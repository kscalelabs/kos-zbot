import threading
import time
from kos_zbot.scservo_sdk import *
from typing import Dict, Optional
import os
import sched
import platform
from tabulate import tabulate  # Add this import at the top of the file

ADDR_KP = 21  # Speed loop P gain
ADDR_KD = 22  # Speed loop D gain


servoRegs = [
    { "name": "Model", "addr": SMS_STS_MODEL_L, "size": 2, "type": "uint16"},
    { "name": "ID", "addr": SMS_STS_ID, "size": 1, "type": "uint8" },
    { "name": "Baudrate", "addr": SMS_STS_BAUD_RATE, "size": 1, "type": "uint8" },
    { "name": "Return Delay", "addr": 7, "size": 1, "type": "uint8" },
    { "name": "Response Status Level", "addr": 8, "size": 1, "type": "uint8" },
    { "name": "Min Angle Limit", "addr": SMS_STS_MIN_ANGLE_LIMIT_L, "size": 2, "type": "uint16" },
    { "name": "Max Angle Limit", "addr": SMS_STS_MAX_ANGLE_LIMIT_L, "size": 2, "type": "uint16" },
    { "name": "Max Temperature Limit", "addr": 13, "size": 1, "type": "uint8" },
    { "name": "Max Voltage Limit", "addr": 14, "size": 1, "type": "uint8" },
    { "name": "Min Voltage Limit", "addr": 15, "size": 1, "type": "uint8" },
    { "name": "Max Torque Limit", "addr": 16, "size": 2, "type": "uint16" },
    { "name": "Phase", "addr": 18, "size": 1, "type": "uint8"},
    { "name": "Unloading Condition", "addr": 19, "size": 1, "type": "uint8" },
    { "name": "LED Alarm Condition", "addr": 20, "size": 1, "type": "uint8" },
    { "name": "P Coefficient", "addr": 21, "size": 1, "type": "uint8" },
    { "name": "D Coefficient", "addr": 22, "size": 1, "type": "uint8" },
    { "name": "I Coefficient", "addr": 23, "size": 1, "type": "uint8" },
    { "name": "Minimum Startup Force", "addr": 24, "size": 2, "type": "uint16" },
    { "name": "CW Dead Zone", "addr": SMS_STS_CW_DEAD, "size": 1, "type": "uint8" },
    { "name": "CCW Dead Zone", "addr": SMS_STS_CCW_DEAD, "size": 1, "type": "uint8" },
    { "name": "Protection Current", "addr": 28, "size": 2, "type": "uint16" },
    { "name": "Angular Resolution", "addr": 30, "size": 1, "type": "uint8" },
    { "name": "Offset", "addr": SMS_STS_OFS_L, "size": 2, "type": "uint16" },
    { "name": "Mode", "addr": SMS_STS_MODE, "size": 1, "type": "uint8" },
    { "name": "Protective Torque", "addr": 34, "size": 1, "type": "uint8" },
    { "name": "Protection Time", "addr": 35, "size": 1, "type": "uint8" },
    { "name": "Overload Torque", "addr": 36, "size": 1, "type": "uint8" },
    { "name": "Speed closed loop P proportional coefficient", "addr": 37, "size": 1, "type": "uint8" },
    { "name": "Over Current Protection Time", "addr": 38, "size": 1, "type": "uint8" },
    { "name": "Velocity closed loop I integral coefficient", "addr": 39, "size": 1, "type": "uint8" },
    { "name": "Torque Enable", "addr": SMS_STS_TORQUE_ENABLE, "size": 1, "type": "uint8" },
    { "name": "Acceleration", "addr": SMS_STS_ACC, "size": 1, "type": "uint8" },
    { "name": "Goal Position", "addr": SMS_STS_GOAL_POSITION_L, "size": 2, "type": "uint16" },
    { "name": "Goal Time", "addr": SMS_STS_GOAL_TIME_L, "size": 2, "type": "uint16" },
    { "name": "Goal Speed", "addr": SMS_STS_GOAL_SPEED_L, "size": 2, "type": "int16" },
    { "name": "Lock", "addr": SMS_STS_LOCK, "size": 1, "type": "uint8" },
    { "name": "Present Position", "addr": SMS_STS_PRESENT_POSITION_L, "size": 2, "type": "uint16" },
    { "name": "Present Speed", "addr": SMS_STS_PRESENT_SPEED_L, "size": 2, "type": "int16" },
    { "name": "Present Load", "addr": SMS_STS_PRESENT_LOAD_L, "size": 2, "type": "int16" },
    { "name": "Present Voltage", "addr": SMS_STS_PRESENT_VOLTAGE, "size": 1, "type": "uint8" },
    { "name": "Present Temperature", "addr": SMS_STS_PRESENT_TEMPERATURE, "size": 1, "type": "uint8" },
    { "name": "Status", "addr": 65, "size": 1, "type": "uint8"},
    { "name": "Moving", "addr": SMS_STS_MOVING, "size": 1, "type": "uint8" },
    { "name": "Present Current", "addr": SMS_STS_PRESENT_CURRENT_L, "size": 2, "type": "uint16" },
    { "name": "Default Moving Threshold", "addr": SMS_STS_DEFAULT_MOVING_THRESHOLD, "size": 1, "type": "uint8" },
    { "name": "Default DTS", "addr": SMS_STS_DEFAULT_DTS_MS, "size": 1, "type": "uint8" },
    { "name": "Default VK", "addr": SMS_STS_DEFAULT_VK_MS, "size": 1, "type": "uint8" },
    { "name": "Default VMIN", "addr": SMS_STS_DEFAULT_VMIN, "size": 1, "type": "uint8" },
    { "name": "Default VMAX", "addr": SMS_STS_DEFAULT_VMAX, "size": 1, "type": "uint8" },
    { "name": "Default AMAX", "addr": SMS_STS_DEFAULT_AMAX, "size": 1, "type": "uint8" },
    { "name": "Default KACC", "addr": SMS_STS_DEFAULT_KACC, "size": 1, "type": "uint8" },
]


class SCSMotorController:
    def __init__(self, device='/dev/ttyAMA5', baudrate=500000, rate=50, actuator_ids=None):
        """Initialize the motor controller with minimal setup"""
        self.rate = rate
        self.period = 1.0 / rate
        self.scheduler = sched.scheduler(time.time, time.sleep)
        
        self.last_config_time = 0
        self.CONFIG_GRACE_PERIOD = 2.0  # Wait 1 second after configs

        self.torque_enabled_ids = set() 

        self.actuator_ids = set()  # Use set instead of list for efficient membership testing
        self.last_commanded_positions = {}
        self.next_position_batch = None  # Atomic batch update
        
        self.port_handler = PortHandler(device)
        self.packet_handler = sms_sts(self.port_handler)
        
        self.port_handler.setBaudRate(baudrate)
        if not self.port_handler.openPort():
            raise RuntimeError("Failed to open the port")
        print(f"Port opened at {self.port_handler.getBaudRate()} baud") 
            
        self.group_sync_read = GroupSyncRead(self.packet_handler, SMS_STS_PRESENT_POSITION_L, 2)
        self.group_sync_write = GroupSyncWrite(self.packet_handler, SMS_STS_GOAL_POSITION_L, 2)
        
        # State variables
        self.running = False
        self.current_positions = {}
        
        # Locks
        self.lock = threading.Lock()
        self.config_lock = threading.Lock()
        self.target_positions_lock = threading.Lock()

        time.sleep(1)
        # Initialize thread
        self.thread = threading.Thread(target=self._update_loop, daemon=True)

    
    def add_actuator(self, actuator_id: int) -> bool:
        """Add a new actuator to the controller"""
        if actuator_id in self.actuator_ids:
            return True
            
        if not self.group_sync_read.addParam(actuator_id):
            print(f"[ID:{actuator_id:03d}] groupSyncRead addparam failed")
            return False
        
        # Initialize position tracking
        self.actuator_ids.add(actuator_id)
        self.last_commanded_positions[actuator_id] = 0
        self.current_positions[actuator_id] = 0
        return True

    def remove_actuator(self, actuator_id: int): #TODO: It's not clear that we really need this
        """Remove an actuator from the controller"""
        if actuator_id in self.actuator_ids:
            self.actuator_ids.remove(actuator_id)
            self.last_commanded_positions.pop(actuator_id, None)
            self.current_positions.pop(actuator_id, None)
    

    def configure_actuator(self, actuator_id: int, config: dict):
        """Configure PD gains and acceleration for a specific actuator"""
        try:
            self.last_config_time = time.monotonic()

            # Get values from config with defaults
            kp = config.get('kp', 20)
            kd = config.get('kd', 10)
            torque_enabled = config.get('torque_enabled', False)
            acceleration = config.get('acceleration', 0) / 100.0
            
            # Ensure values are within valid ranges
            kp = max(0, min(255, int(kp)))
            kd = max(0, min(255, int(kd)))
            acceleration = max(0, min(255, int(acceleration)))

            with self.config_lock:
                # First add the actuator
                if not self.add_actuator(actuator_id):
                    print(f"Failed to add actuator {actuator_id}")
                    return False


            success = True
            # Write KP
            success &= self.writeReg(actuator_id, ADDR_KP, kp)
            if not success:
                print(f"Failed to write KP for actuator {actuator_id}")
                return False
            
            # Write KD
            success &= self.writeReg(actuator_id, ADDR_KD, kd)
            if not success:
                print(f"Failed to write KD for actuator {actuator_id}")
                return False
            
            # Write ACC
            success &= self.writeReg(actuator_id, SMS_STS_ACC, acceleration)
            if not success:
                print(f"Failed to write ACC for actuator {actuator_id}")
                return False

            success &= self.writeReg(actuator_id, SMS_STS_TORQUE_ENABLE, 1 if torque_enabled else 0)
            if not success:
                print(f"Failed to set torque enable for actuator {actuator_id}")
                return False

            if torque_enabled:
                self.torque_enabled_ids.add(actuator_id)
            else:
                self.torque_enabled_ids.discard(actuator_id)

            # Handle zero position first if requested
            if config.get('zero_position', False):
                self.set_zero_position(actuator_id)

            if success:
                print(f"Actuator {actuator_id} configured successfully: kp={kp}, kd={kd}, acc={acceleration}, torque={'on' if torque_enabled else 'off'}")
            else:
                self.remove_actuator(actuator_id)
                print(f"Actuator {actuator_id} configuration failed")
            return success

        except Exception as e:
            print(f"Error configuring actuator {actuator_id}: {str(e)}")
            self.remove_actuator(actuator_id)
            return False


    #TODO: Make this comprehensive and put into use
    async def _verify_config(self, actuator_id: int, config: dict):
        """Verify that configuration was applied correctly."""
        try:
            if "acceleration" in config:
                # Read back acceleration value
                actual_acc = packet_handler.read1ByteTxRx(actuator_id, SMS_STS_ACC)
                if actual_acc != config["acceleration"]:
                    print(f"Acceleration mismatch: expected {config['acceleration']}, got {actual_acc}")
                    return False

            # Add other configuration verifications here
            return True

        except Exception as e:
            print(f"Verification error: {str(e)}")
            return False

    def start(self):
        """Start the motor controller update loop with real-time priority"""
        self.running = True
        
        # Set real-time priority if possible
        if platform.system() == 'Linux':
            try:
                os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(99))
            except PermissionError:
                print("Warning: Could not set real-time priority")
                
        self.thread.start()

        
    def stop(self):
        """Stop the motor controller update loop"""
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
        self.port_handler.closePort()
        
    
    def _update_loop(self):
        """Main update loop running at specified rate with precise timing"""
        next_time = time.monotonic()
        
        while self.running:
            current_time = time.monotonic()
            
            # Only perform read/write if enough time has passed since last config
            if current_time - self.last_config_time >= self.CONFIG_GRACE_PERIOD:
                try:
                    with self.config_lock:
                        if self.actuator_ids:
                            self._read_positions()
                            self._write_positions()
                except Exception as e:
                    print(f"Error in update loop: {e}")
            
            # Precise timing control using monotonic time
            next_time += self.period
            sleep_time = next_time - time.monotonic()
            
            if sleep_time > 0:
                # For sub-millisecond precision, use busy waiting for the last bit
                target_time = time.monotonic() + sleep_time
                long_sleep = sleep_time - 0.001  # Leave 1ms for fine adjustment
                
                if long_sleep > 0:
                    time.sleep(long_sleep)
                    
                # Busy-wait for the remainder
                while time.monotonic() < target_time:
                    pass
            else:
                # If we're behind, reset timing instead of trying to catch up
                next_time = time.monotonic() + self.period
                print("Timing overrun detected")


    def _get_params(self, actuator_id: int) -> dict:
        """Read current KP, KD, and acceleration parameters from a servo
        
        Args:
            actuator_id: ID of the servo to read from
            
        Returns:
            Dictionary containing the current parameters, or None if read fails
        """
        try:
            # Read KP
            kp_result, kp_error, kp = self.packet_handler.read1ByteTxRx(actuator_id, ADDR_KP)
            if kp_result != 0:
                print(f"Failed to read KP from actuator {actuator_id}")
                return None
                
            # Read KD
            kd_result, kd_error, kd = self.packet_handler.read1ByteTxRx(actuator_id, ADDR_KD)
            if kd_result != 0:
                print(f"Failed to read KD from actuator {actuator_id}")
                return None
                
            # Read Acceleration
            acc_result, acc_error, acc = self.packet_handler.read1ByteTxRx(actuator_id, SMS_STS_ACC)
            if acc_result != 0:
                print(f"Failed to read ACC from actuator {actuator_id}")
                return None
                
            # Read torque enable state
            torque_result, torque_error, torque = self.packet_handler.read1ByteTxRx(actuator_id, SMS_STS_TORQUE_ENABLE)
            if torque_result != 0:
                print(f"Failed to read torque enable from actuator {actuator_id}")
                return None

            params = {
                'kp': kp,
                'kd': kd,
                'acceleration': acc * 100,  # Convert back to percentage
                'torque_enabled': bool(torque)
            }
            print(f"Actuator {actuator_id} parameters: KP: {params['kp']}, KD: {params['kd']}, Acceleration: {params['acceleration']}%, Torque enabled: {params['torque_enabled']}")
            
            return params

        except Exception as e:
            print(f"Error reading parameters from actuator {actuator_id}: {str(e)}")
            return None
            
    def get_all_params(self):
        """Read and display parameters for all configured actuators"""
        print("Reading parameters for all actuators...")
        for actuator_id in sorted(self.actuator_ids):
            self._get_params(actuator_id)
            print()  # Add blank line between actuators
            
    def _read_positions(self):
        """Read current positions from all servos"""
        scs_comm_result = self.group_sync_read.txRxPacket()
        if scs_comm_result != 0:
            print(f"Read error: {self.packet_handler.getTxRxResult(scs_comm_result)}")
            return
            
        with self.lock:
            for actuator_id in self.actuator_ids:
                data_result, error = self.group_sync_read.isAvailable(actuator_id, SMS_STS_PRESENT_POSITION_L, 2)
                if data_result and error == 0:
                    position = self.group_sync_read.getData(actuator_id, SMS_STS_PRESENT_POSITION_L, 2)
                    self.current_positions[actuator_id] = position
    

    def _write_positions(self):
        """Write positions to all servos synchronously"""
        if not self.torque_enabled_ids:
            return

        # Update our target if there are new positions
        with self.target_positions_lock:
            if self.next_position_batch is not None:
                self.last_commanded_positions = self.next_position_batch
                self.next_position_batch = None

        self.group_sync_write.clearParam()
        for actuator_id in sorted(self.torque_enabled_ids):
            position = self.last_commanded_positions.get(actuator_id, 0)
            position_data = [
                self.packet_handler.scs_lobyte(int(position)),
                self.packet_handler.scs_hibyte(int(position))
            ]
            self.group_sync_write.addParam(actuator_id, position_data)
        self.group_sync_write.txPacket()

            
    def set_positions(self, position_dict: Dict[int, float]):
        """Set target positions for multiple actuators atomically"""
        with self.target_positions_lock:
            # Create new batch by updating existing positions with new ones
            if self.next_position_batch is None:
                self.next_position_batch = self.last_commanded_positions.copy()
            self.next_position_batch.update(position_dict)
            
    def get_position(self, actuator_id: int) -> Optional[float]:
        """Get current position of a specific actuator"""
        with self.lock:
            return self.current_positions.get(actuator_id)

    def get_torque_enabled(self, actuator_id: int) -> bool:
        return actuator_id in self.torque_enabled_ids

    def _unlockEEPROM(self, actuator_id):
        self.packet_handler.unLockEprom(actuator_id)
        print("EEPROM unlocked")

    def _lockEEPROM(self, actuator_id):
        self.packet_handler.LockEprom(actuator_id)
        print("EEPROM locked")


    def writeReg(self, actuator_id, regAddr, value):
        """Write to a register with retries. Returns True if successful, False otherwise."""
        reg = None
        for r in servoRegs:
            if r["addr"] == regAddr:
                reg = r
                break

        if reg == None:
            print("Unknown register: " + str(regAddr))
            return False  # Return False instead of None
        
        if reg["size"] == 2:
            value = [self.packet_handler.scs_lobyte(value), self.packet_handler.scs_hibyte(value)]
        else:
            value = [value]
        
        retries = 3
        while retries > 0:
            comm_result, error = self.packet_handler.writeTxRx(actuator_id, regAddr, reg["size"], value)
            if comm_result == 0:
                #print(f"Register {regAddr} written")
                return True
            else:
                print("Failed to write register - retrying...")
                retries -= 1
        
        print(f"Failed to write register {regAddr} after all retries")
        return False  # Return False after all retries fail

    def _get_model_name(self, model_number):
        """Translate model number to human-readable name"""
        model_map = {
            777: "STS3215",   # 0x0309
            2825: "STS3250"   # 0x0B09
        }
        return model_map.get(model_number, f"Unknown Model {model_number}")

    def read_all_servo_params(self, actuator_id: int, show_results=True):
        """Read and display all relevant parameters for a servo"""
        try:
            params = {}
            if show_results:
                print(f"\n=== Actuator {actuator_id} Parameters ===")
            
            for reg in servoRegs:
                try:
                    value, comm_result, error = self.packet_handler.readTxRx(actuator_id, reg["addr"], reg["size"])
                    
                    if comm_result == COMM_SUCCESS:
                        if reg["size"] == 2:
                            value = self.packet_handler.scs_tohost(
                                self.packet_handler.scs_makeword(value[0], value[1]), 
                                15
                            )
                        else:
                            value = value[0]
                        
                        # Special handling for Model - store the name instead of the number
                        if reg["name"] == "Model":
                            value = self._get_model_name(value)
                            
                        params[reg["name"]] = value
                        if show_results:
                            print(f"{reg['name']}: {value}")
                    else:
                        if show_results:
                            print(f"Failed to read {reg['name']} - {self.packet_handler.getTxRxResult(comm_result)}")
                        
                except Exception as e:
                    print(f"Error reading {reg['name']} (addr: {reg['addr']}): {str(e)}")
                    continue
                    
            # Add derived values
            if "Present Position" in params and show_results:
                degrees = (params["Present Position"] * 360 / 4095) - 180
                print(f"Position in degrees: {degrees:.2f}°")
                
            if show_results:
                print("=" * 30)
            return params
                
        except Exception as e:
            print(f"Error reading parameters from actuator {actuator_id}: {str(e)}")
            return None

    def read_all_servos_params(self):
        """Read and display parameters for all configured actuators"""
        print("\nReading all parameters for configured actuators...")
        results = {}
        for actuator_id in sorted(self.actuator_ids):
            results[actuator_id] = self.read_all_servo_params(actuator_id, show_results=False)
        return results


    def compare_actuator_params(self, actuator_ids=None, params_to_compare=None):
        """Compare specific parameters across multiple actuators and show differences."""
        # Use all servoRegs by default, creating display names with register addresses
        default_params = [reg["name"] for reg in servoRegs]
        
        params_to_compare = params_to_compare or default_params
        actuator_ids = sorted(actuator_ids or self.actuator_ids)
        
        if len(actuator_ids) < 2:
            print("Need at least 2 actuators to compare")
            return
        
        # Read all parameters for specified actuators
        actuator_params = {}
        for aid in actuator_ids:
            actuator_params[aid] = self.read_all_servo_params(aid, show_results=False)
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
                    f"\033[91m{v}\033[0m" if v != base_value_str else v 
                    for v in row[1:]
                ]
            table_data.append(row)
        
        print("\n=== Parameter Comparison ===")
        print(f"Comparing actuators: {actuator_ids}")
        print(tabulate(
            table_data,
            headers=headers,
            tablefmt="grid",
            numalign="right",
            stralign="left"
        ))
        
        if not differences_found:
            print("\nAll compared parameters are identical across actuators.")
        
        return actuator_params

    def set_zero_position(self, actuator_id: int):
        self._unlockEEPROM(actuator_id)
        time.sleep(0.01)
        
        # Set min angle to 0
        self.writeReg(actuator_id, SMS_STS_MIN_ANGLE_LIMIT_L, 0x0000)
        time.sleep(0.01)
        
        # Set max angle to 4095
        self.writeReg(actuator_id, SMS_STS_MAX_ANGLE_LIMIT_L, 0x0FFF)
        time.sleep(0.01)
        
        # Set position control mode
        self.writeReg(actuator_id, SMS_STS_MODE, 0)
        time.sleep(0.01)
        
        # Enable torque with special flag
        self.writeReg(actuator_id, SMS_STS_TORQUE_ENABLE, 0x80)
        time.sleep(0.01)
        
        self._lockEEPROM(actuator_id)