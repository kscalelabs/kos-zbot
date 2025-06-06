from .packet_handler import packet_handler
from .servo_defs import *

class ServoInterface(packet_handler):
    def __init__(self, portHandler, protocol_end=0):
        super().__init__(portHandler, protocol_end)
    
    def unlockEEPROM(self, actuator_id):
        return self.write1ByteTxRx(actuator_id, SMS_STS_LOCK, 0)

    def lockEEPROM(self, actuator_id):
        return self.write1ByteTxRx(actuator_id, SMS_STS_LOCK, 1)

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


