from .packet_handler import packet_handler
from .servo_defs import *
import time
from tqdm import tqdm
from tabulate import tabulate

class ServoInterface(packet_handler):
    def __init__(self, portHandler, protocol_end=0):
        super().__init__(portHandler, protocol_end)
    
    def unlockEEPROM(self, actuator_id):
        return self.write1ByteTxRx(actuator_id, SMS_STS_LOCK, 0)

    def lockEEPROM(self, actuator_id):
        return self.write1ByteTxRx(actuator_id, SMS_STS_LOCK, 1)

    def counts_to_degrees(self, counts: float, offset: float = 180.0) -> float:
        """Convert raw counts to degrees with optional offset"""
        return (counts * 360 / 4096) - offset

    def degrees_to_counts(self, degrees: float, offset: float = 180.0) -> int:
        """Convert degrees to raw counts with optional offset"""
        return int((degrees + offset) * (4096 / 360))

    def writeReg_Verify(self, actuator_id, regAddr, value):
            """Write to a register with retries. Returns True if successful, False otherwise."""
            reg = None
            for r in servoRegs:
                if r["addr"] == regAddr:
                    reg = r
                    break

            if reg == None:
                self.log.error("unknown register: " + str(regAddr))
                return False  # Return False instead of None

            if reg["size"] == 2:
                value = [
                    self.scs_lobyte(value),
                    self.scs_hibyte(value),
                ]
            else:
                value = [value]

            retries = 3
            while retries > 0:
                comm_result, error = self.writeTxRx(
                    actuator_id, regAddr, reg["size"], value
                )
                if comm_result == 0:
                    # print(f"Register {regAddr} written")
                    return True
                else:
                    self.log.error(
                        f"Write to ID: {actuator_id} Register: {regAddr} - {self.getTxRxResult(comm_result)} - retrying {retries} times: "
                    )
                    retries -= 1

            # self.log.error(f"failed to write register {regAddr} after all retries")
            return False  # Return False after all retries fail

    def writeReg(self, actuator_id, regAddr, value):
        """Write to a register with retries. Returns True if successful, False otherwise."""
        reg = None
        for r in servoRegs:
            if r["addr"] == regAddr:
                reg = r
                break

        if reg == None:
            self.log.error("unknown register: " + str(regAddr))
            return False

        if reg["size"] == 2:
            value = [
                self.scs_lobyte(value),
                self.scs_hibyte(value),
            ]
        else:
            value = [value]

        comm_result = self.writeTxOnly(
            actuator_id, regAddr, reg["size"], value
        )
        if comm_result == 0:
            return True

        self.log.error(
            f"Write to ID: {actuator_id} Register: {regAddr} - {self.getTxRxResult(comm_result)}"
        )
        return False

    def get_model_name(self, model_number):
        """Translate model number to human-readable name"""
        model_map = {777: "STS3215", 2825: "STS3250"}  # 0x0309  # 0x0B09
        return model_map.get(model_number, f"Unknown Model {model_number}")


    def change_id(self, current_id: int, new_id: int) -> bool:
        """
        Change the ID of a servo on the bus.

        Args:
            current_id: Current ID of the servo (0-253)
            new_id: New ID to set for the servo (0-253)
        Returns:
            True if the ID change was successful
        """
        if not (0 <= current_id <= 253 and 0 <= new_id <= 253):
            self.log.error("IDs must be between 0 and 253")
            return False

        self.log.info(f"Changing servo ID from {current_id} to {new_id}")
        success = True

        # unlock EEPROM
        self._unlockEEPROM(current_id)
        time.sleep(0.01)

        # write new ID
        if not self.writeReg_Verify(current_id, SMS_STS_ID, new_id):
            self.log.error(f"Failed to write new ID {new_id} to servo {current_id}")
            success = False

        time.sleep(0.01)
        # lock EEPROM again
        self.lockEEPROM
        time.sleep(0.01)

        return success


    def change_baudrate(self, raw_baud: int) -> bool:
        """
        Set bus speed by passing the actual baud rate.

        Args:
            raw_baud: one of 1_000_000, 500_000, or 250_000
            verify: if True, read back each servo’s baud‐rate register to confirm
        Returns:
            True if all writes (and host port update) succeeded
        """
        # map actual baud → register index
        baud_to_index = {
            1_000_000: 0,  # index 0 => 1 Mbps
            500_000: 1,  # index 1 => 500 kbps
            250_000: 2,  # index 2 => 250 kbps
        }
        if raw_baud not in baud_to_index:
            self.log.error(f"Unsupported baud rate: {raw_baud}")
            return False

        idx = baud_to_index[raw_baud]
        self.log.info(f"idx: {idx}")
        success = True

    
        for aid in sorted(self.actuator_ids):
            self.log.info(f"Changing baudrate for actuator {aid} to {raw_baud}")
            # unlock EEPROM
            self.unlockEEPROM(aid)
            time.sleep(0.01)

            # write index into the baud‐rate register
            if not self.writeReg(aid, SMS_STS_BAUD_RATE, idx):
                # self.log.error(f"[id:{aid:03d}] failed to write baud index {idx}")
                success = False

            time.sleep(0.01)
            # lock EEPROM again
            self.lockEEPROM(aid)
            time.sleep(0.01)

        return success

    
    def scan_servos(self, id_range: range) -> list:
        found_servos = []
        found_strings = []
        with tqdm(id_range, desc="Scanning servos", unit="ID") as pbar:
            for servo_id in pbar:
                model_number, result, error = self.ping(servo_id)
                if result == 0:
                    model_name = self.get_model_name(model_number)
                    found_servos.append({"id": servo_id, "model": model_name})
                    found_strings.append(f"[{servo_id} {model_name}]")
        if found_strings:
            self.log.info("Found servos: " + ", ".join(found_strings))
        else:
            self.log.info("No servos found.")
        return found_servos

    def set_zero_position(self, actuator_id: int):
        self.unlockEEPROM(actuator_id)
        time.sleep(0.01)

        # Set min angle to 0
        self.writeReg_Verify(actuator_id, SMS_STS_MIN_ANGLE_LIMIT_L, 0x0000)
        time.sleep(0.01)

        # Set max angle to 4095
        self.writeReg_Verify(actuator_id, SMS_STS_MAX_ANGLE_LIMIT_L, 0x0FFF)
        time.sleep(0.01)

        # Set position control mode
        self.writeReg_Verify(actuator_id, SMS_STS_MODE, 0)
        time.sleep(0.01)

        # Enable torque with special flag
        self.writeReg_Verify(actuator_id, SMS_STS_TORQUE_ENABLE, 0x80)
        time.sleep(0.01)

        self.lockEEPROM(actuator_id)

        # Set the target and buffers to zero
        self.last_commanded_positions[actuator_id] = self.degrees_to_counts(
            0, offset=180.0
        )
        self.last_commanded_velocities[actuator_id] = 0
        self._positions_a[actuator_id] = 0
        self._positions_b[actuator_id] = 0

    def read_all_servo_params(self, actuator_id: int):
        """Read and display all relevant parameters for a servo"""
        try:
            params = {}
            for reg in servoRegs:
                try:
                    value, comm_result, error = self.readTxRx(
                        actuator_id, reg["addr"], reg["size"]
                    )

                    if comm_result == COMM_SUCCESS:
                        if reg["size"] == 2:
                            value = self.scs_tohost(
                                self.scs_makeword(
                                    value[0], value[1]
                                ),
                                15,
                            )
                        else:
                            value = value[0]

                        # Special handling for Model - store the name instead of the number
                        if reg["name"] == "Model":
                            value = self.get_model_name(value)

                        params[reg["name"]] = {"value": value, "addr": reg["addr"]}
                    else:
                        self.log.error(
                            f"Read ID: {actuator_id} Register: {reg['addr']} - {self.getTxRxResult(comm_result)}"
                        )

                except Exception as e:
                    self.log.error(
                        f"error reading {reg['name']} (addr: {reg['addr']}): {str(e)}"
                    )
                    continue
            return params

        except Exception as e:
            self.log.error(
                f"error reading parameters from actuator {actuator_id}: {str(e)}"
            )
            return None


    def compare_actuator_params(self, actuator_ids=None, params_to_compare=None):
        """Compare specific parameters across multiple actuators and show differences."""
        # Use all servoRegs by default, creating display names with register addresses
        default_params = [reg["name"] for reg in servoRegs]

        params_to_compare = params_to_compare or default_params
        actuator_ids = sorted(actuator_ids or self.actuator_ids)

        if len(actuator_ids) < 2:
            print("need at least 2 actuators to compare")
            return

        # Read all parameters for specified actuators
        actuator_params = {}
        for aid in actuator_ids:
            actuator_params[aid] = self.read_all_servo_params(aid)
            time.sleep(0.1)

        # Create a mapping of parameter names to their register addresses
        reg_addresses = {reg["name"]: reg["addr"] for reg in servoRegs}

        # Prepare table data
        headers = ["Parameter [Reg]"] + [f"ID {aid}" for aid in actuator_ids]
        table_data = []
        differences_found = False

        for param in params_to_compare:
            # Create parameter name with register address
            param_with_reg = f"{param} [{reg_addresses[param]}]"
            row = [param_with_reg]
            base_value = None
            row_has_diff = False

            # Collect values for this parameter
            for aid in actuator_ids:
                if actuator_params[aid] and param in actuator_params[aid]:
                    value = actuator_params[aid][param]
                    value_str = str(value)

                    if base_value is None:
                        base_value = value
                        base_value_str = value_str
                    elif value != base_value:
                        row_has_diff = True
                    row.append(value_str)
                else:
                    row.append("N/A")
                    row_has_diff = True

            if row_has_diff:
                differences_found = True
                row = [row[0]] + [
                    f"\033[91m{v}\033[0m" if v != base_value_str else v for v in row[1:]
                ]
            table_data.append(row)

        print("\n=== Parameter Comparison ===")
        print(f"Comparing actuators: {actuator_ids}")
        print(
            tabulate(
                table_data,
                headers=headers,
                tablefmt="grid",
                numalign="right",
                stralign="left",
            )
        )

        if not differences_found:
            print("\nAll compared parameters are identical across actuators.")

        return actuator_params
