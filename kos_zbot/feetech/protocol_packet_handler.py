#!/usr/bin/env python

from .scservo_def import *
from kos_zbot.utils.logging import get_logger

# ──────────────────────────────────────────────────────────────────────────────
# Protocol‑level constants (SCServo / Dynamixel v1)
HDR_BYTE          = 0xFF
HEADER            = bytes((HDR_BYTE, HDR_BYTE))

PKT_ID            = 2          # index
PKT_LENGTH        = 3
PKT_INSTRUCTION     = 4
PKT_ERROR         = 4
PKT_PARAMETER0 = 5

ID_BROADCAST_MAX  = 0xFD       # 0xFE=Broadcast, 0xFF=Reserved
ERR_MASK_MAX      = 0x7F       # bits 7.. have other uses in some variants
RXPACKET_MAX_LEN  = 250

CORE_LEN          = 2          # ID + LEN
ERR_LEN           = 1
CHK_LEN           = 1
MIN_FRAME_LEN     = len(HEADER) + CORE_LEN + ERR_LEN + CHK_LEN  # -> 6

TXPACKET_MAX_LEN = 250
RXPACKET_MAX_LEN = 250
# ──────────────────────────────────────────────────────────────────────────────


class protocol_packet_handler(object):
    def __init__(self, portHandler, protocol_end):
        #self.scs_setend(protocol_end)# SCServo bit end(STS/SMS=0, SCS=1)
        self.portHandler = portHandler
        self.scs_end = protocol_end
        self.CHAR_TIME_US = 10.0 * 1_000_000 / self.portHandler.baudrate  # 10 bits/char (example: 500000 baud --> 20us per byte)

        # TODO: Analyze this idle gap logic with a logic analyzer and confirm this is legit (find the right value)
        self.IDLE_GAP_US = self.CHAR_TIME_US * 20                         # 2‑char idle gap (example: 500000 baud --> 40us)
        self.log = get_logger(__name__)

    def scs_getend(self):
        return self.scs_end

    def scs_setend(self, e):
        self.scs_end = e

    def scs_tohost(self, a, b):
        if (a & (1<<b)):
            return -(a & ~(1<<b))
        else:
            return a

    def scs_toscs(self, a, b):
        if (a<0):
            return (-a | (1<<b))
        else:
            return a

    def scs_makeword(self, a, b):
        if self.scs_end==0:
            return (a & 0xFF) | ((b & 0xFF) << 8)
        else:
            return (b & 0xFF) | ((a & 0xFF) << 8)

    def scs_makedword(self, a, b):
        return (a & 0xFFFF) | (b & 0xFFFF) << 16

    def scs_loword(self, l):
        return l & 0xFFFF

    def scs_hiword(self, h):
        return (h >> 16) & 0xFFFF

    def scs_lobyte(self, w):
        if self.scs_end==0:
            return w & 0xFF
        else:
            return (w >> 8) & 0xFF

    def scs_hibyte(self, w):
        if self.scs_end==0:
            return (w >> 8) & 0xFF
        else:
            return w & 0xFF
        
    def getProtocolVersion(self):
        return 1.0

    def getTxRxResult(self, result):
        if result == COMM_SUCCESS:
            return "[TxRxResult] Communication success!"
        elif result == COMM_PORT_BUSY:
            return "[TxRxResult] Port is in use!"
        elif result == COMM_TX_FAIL:
            return "[TxRxResult] Failed transmit instruction packet!"
        elif result == COMM_RX_FAIL:
            return "[TxRxResult] Failed get status packet from device!"
        elif result == COMM_TX_ERROR:
            return "[TxRxResult] Incorrect instruction packet!"
        elif result == COMM_RX_WAITING:
            return "[TxRxResult] Now receiving status packet!"
        elif result == COMM_RX_TIMEOUT:
            return "[TxRxResult] RX Timeout (status packet)"
        elif result == COMM_RX_CORRUPT:
            return "[TxRxResult] RX corrupt (status packet)"
        elif result == COMM_NOT_AVAILABLE:
            return "[TxRxResult] Protocol does not support this function!"
        else:
            return ""

    def getRxPacketError(self, error):
        if error & ERRBIT_VOLTAGE:
            return "[ServoStatus] Input voltage error!"

        if error & ERRBIT_ANGLE:
            return "[ServoStatus] Angle sen error!"

        if error & ERRBIT_OVERHEAT:
            return "[ServoStatus] Overheat error!"

        if error & ERRBIT_OVERELE:
            return "[ServoStatus] OverEle error!"
        
        if error & ERRBIT_OVERLOAD:
            return "[ServoStatus] Overload error!"

        return ""

    def txPacket(self, txpacket):
        checksum = 0
        total_packet_length = txpacket[PKT_LENGTH] + 4  # 4: HEADER0 HEADER1 ID LENGTH

        if self.portHandler.is_using:
            return COMM_PORT_BUSY
        self.portHandler.is_using = True

        # check max packet length
        if total_packet_length > TXPACKET_MAX_LEN:
            self.portHandler.is_using = False
            return COMM_TX_ERROR

        # make packet header
        txpacket[0:2] = HEADER

        # add a checksum to the packet
        for idx in range(2, total_packet_length - 1):  # except header, checksum
            checksum += txpacket[idx]

        txpacket[total_packet_length - 1] = ~checksum & 0xFF

        #print "[TxPacket] %r" % txpacket

        # tx packet
        self.portHandler.clearPort()
        written_packet_length = self.portHandler.writePort(txpacket)
        if total_packet_length != written_packet_length:
            self.portHandler.is_using = False
            return COMM_TX_FAIL

        return COMM_SUCCESS




    def rxPacket(self):
        """
        Blocking receive‑and‑parse for a single status packet.
        Returns (bytes(rx_packet), result_code)
        """
        rxpacket         = bytearray()
        result           = None                         # CHANGED: clearer init
        wait_length      = MIN_FRAME_LEN
        last_byte_us     = self.portHandler.getCurrentTime_us()
        first_byte_seen  = False

        # mark port busy until we exit, even on exception
        self.portHandler.is_using = True                # CHANGED: moved to top
        try:
            while True:
                chunk = self.portHandler.readPort(wait_length - len(rxpacket))
                if chunk:
                    rxpacket.extend(chunk)
                    last_byte_us    = self.portHandler.getCurrentTime_us()
                    first_byte_seen = True
                else:
                    # ── GAP DETECTION ────────────────────────────────────────────
                    if (first_byte_seen and
                        self.portHandler.getCurrentTime_us() - last_byte_us
                            > self.IDLE_GAP_US):
                        self.log.debug("RX gap > idle threshold → abort")  # CHANGED: print→log
                        result = COMM_RX_CORRUPT
                        break

                # ── Have we read enough yet? ────────────────────────────────────
                if len(rxpacket) < wait_length:
                    if self.portHandler.isPacketTimeout():
                        result = (COMM_RX_TIMEOUT if not rxpacket
                                else COMM_RX_CORRUPT)
                        break
                    continue

                # ── Ensure header alignment ─────────────────────────────────────
                if rxpacket[:2] != HEADER:
                    # discard until we realign on FF FF
                    while len(rxpacket) >= 2 and rxpacket[:2] != HEADER:
                        rxpacket.pop(0)
                    first_byte_seen = False
                    last_byte_us    = self.portHandler.getCurrentTime_us()
                    wait_length     = MIN_FRAME_LEN
                    continue

                # ── Sanity‑check ID, LEN, ERR ──────────────────────────────────
                pkt_len = rxpacket[PKT_LENGTH]
                if (rxpacket[PKT_ID]    > ID_BROADCAST_MAX or
                    pkt_len             > RXPACKET_MAX_LEN or
                    rxpacket[PKT_ERROR] > ERR_MASK_MAX):
                    self.log.debug("Header sane‑check failed → resync")
                    rxpacket.pop(0)                      # drop first 0xFF
                    first_byte_seen = False
                    last_byte_us    = self.portHandler.getCurrentTime_us()
                    wait_length     = MIN_FRAME_LEN
                    continue

                # ── Recompute expected total length ────────────────────────────
                wait_length = 4 + pkt_len               #  2*FF + ID + LEN + LEN bytes
                if len(rxpacket) < wait_length:
                    continue

                # ── CHECKSUM ────────────────────────────────────────────────────
                checksum = (~sum(rxpacket[2:wait_length-1]) & 0xFF)
                result   = (COMM_SUCCESS if rxpacket[wait_length-1] == checksum
                            else COMM_RX_CORRUPT)
                break                                            # done (good or bad)
        finally:
            self.portHandler.is_using = False

        return bytes(rxpacket), result


    def txRxPacket(self, txpacket):
        rxpacket = None
        error = 0

        # tx packet
        result = self.txPacket(txpacket)
        if result != COMM_SUCCESS:
            return rxpacket, result, error

        # (ID == Broadcast ID) == no need to wait for status packet or not available
        if (txpacket[PKT_ID] == BROADCAST_ID):
            self.portHandler.is_using = False
            return rxpacket, result, error

        # set packet timeout
        if txpacket[PKT_INSTRUCTION] == INST_READ:
            self.portHandler.setPacketTimeout(txpacket[PKT_PARAMETER0 + 1] + 6)
        elif txpacket[PKT_INSTRUCTION] == INST_WRITE and txpacket[PKT_PARAMETER0] < 32:  # EEPROM zone? Servo needs time to process
            self.portHandler.setPacketTimeout(6, extra_us=100_000)
        else:
            self.portHandler.setPacketTimeout(6)  # HEADER0 HEADER1 ID LENGTH ERROR CHECKSUM

        # rx packet
        while True:
            rxpacket, result = self.rxPacket()
            if result != COMM_SUCCESS or txpacket[PKT_ID] == rxpacket[PKT_ID]:
                break

        if result == COMM_SUCCESS and txpacket[PKT_ID] == rxpacket[PKT_ID]:
            error = rxpacket[PKT_ERROR]

        return rxpacket, result, error

    def ping(self, scs_id):
        model_number = 0
        error = 0

        txpacket = [0] * 6

        if scs_id >= BROADCAST_ID:
            return model_number, COMM_NOT_AVAILABLE, error

        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = 2
        txpacket[PKT_INSTRUCTION] = INST_PING

        rxpacket, result, error = self.txRxPacket(txpacket)

        if result == COMM_SUCCESS:
            data_read, result, error = self.readTxRx(scs_id, 3, 2)  # Address 3 : Model Number
            if result == COMM_SUCCESS:
                model_number = self.scs_makeword(data_read[0], data_read[1])

        return model_number, result, error

    def action(self, scs_id):
        txpacket = [0] * 6

        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = 2
        txpacket[PKT_INSTRUCTION] = INST_ACTION

        _, result, _ = self.txRxPacket(txpacket)

        return result

    def readTx(self, scs_id, address, length):

        txpacket = [0] * 8

        if scs_id >= BROADCAST_ID:
            return COMM_NOT_AVAILABLE

        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = 4
        txpacket[PKT_INSTRUCTION] = INST_READ
        txpacket[PKT_PARAMETER0 + 0] = address
        txpacket[PKT_PARAMETER0 + 1] = length

        result = self.txPacket(txpacket)

        # set packet timeout
        if result == COMM_SUCCESS:
            self.portHandler.setPacketTimeout(length + 6)

        return result

    def readRx(self, scs_id, length):
        result = COMM_TX_FAIL
        error = 0

        rxpacket = None
        data = []

        while True:
            rxpacket, result = self.rxPacket()

            if result != COMM_SUCCESS or rxpacket[PKT_ID] == scs_id:
                break

        if result == COMM_SUCCESS and rxpacket[PKT_ID] == scs_id:
            error = rxpacket[PKT_ERROR]

            data.extend(rxpacket[PKT_PARAMETER0 : PKT_PARAMETER0+length])

        return data, result, error

    def readTxRx(self, scs_id, address, length):
        txpacket = [0] * 8
        data = []

        if scs_id >= BROADCAST_ID:
            return data, COMM_NOT_AVAILABLE, 0

        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = 4
        txpacket[PKT_INSTRUCTION] = INST_READ
        txpacket[PKT_PARAMETER0 + 0] = address
        txpacket[PKT_PARAMETER0 + 1] = length

        rxpacket, result, error = self.txRxPacket(txpacket)
        if result == COMM_SUCCESS:
            error = rxpacket[PKT_ERROR]

            data.extend(rxpacket[PKT_PARAMETER0 : PKT_PARAMETER0+length])

        return data, result, error

    def read1ByteTx(self, scs_id, address):
        return self.readTx(scs_id, address, 1)

    def read1ByteRx(self, scs_id):
        data, result, error = self.readRx(scs_id, 1)
        data_read = data[0] if (result == COMM_SUCCESS) else 0
        return data_read, result, error

    def read1ByteTxRx(self, scs_id, address):
        data, result, error = self.readTxRx(scs_id, address, 1)
        data_read = data[0] if (result == COMM_SUCCESS) else 0
        return data_read, result, error

    def read2ByteTx(self, scs_id, address):
        return self.readTx(scs_id, address, 2)

    def read2ByteRx(self, scs_id):
        data, result, error = self.readRx(scs_id, 2)
        data_read = self.scs_makeword(data[0], data[1]) if (result == COMM_SUCCESS) else 0
        return data_read, result, error

    def read2ByteTxRx(self, scs_id, address):
        data, result, error = self.readTxRx(scs_id, address, 2)
        data_read = self.scs_makeword(data[0], data[1]) if (result == COMM_SUCCESS) else 0
        return data_read, result, error

    def read4ByteTx(self, scs_id, address):
        return self.readTx(scs_id, address, 4)

    def read4ByteRx(self, scs_id):
        data, result, error = self.readRx(scs_id, 4)
        data_read = self.scs_makedword(self.scs_makeword(data[0], data[1]),
                                  self.scs_makeword(data[2], data[3])) if (result == COMM_SUCCESS) else 0
        return data_read, result, error

    def read4ByteTxRx(self, scs_id, address):
        data, result, error = self.readTxRx(scs_id, address, 4)
        data_read = self.scs_makedword(self.scs_makeword(data[0], data[1]),
                                  self.scs_makeword(data[2], data[3])) if (result == COMM_SUCCESS) else 0
        return data_read, result, error

    def writeTxOnly(self, scs_id, address, length, data):
        txpacket = [0] * (length + 7)

        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = length + 3
        txpacket[PKT_INSTRUCTION] = INST_WRITE
        txpacket[PKT_PARAMETER0] = address

        txpacket[PKT_PARAMETER0 + 1: PKT_PARAMETER0 + 1 + length] = data[0: length]

        result = self.txPacket(txpacket)
        self.portHandler.is_using = False

        return result

    def writeTxRx(self, scs_id, address, length, data):
        txpacket = [0] * (length + 7)

        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = length + 3
        txpacket[PKT_INSTRUCTION] = INST_WRITE
        txpacket[PKT_PARAMETER0] = address

        txpacket[PKT_PARAMETER0 + 1: PKT_PARAMETER0 + 1 + length] = data[0: length]
        rxpacket, result, error = self.txRxPacket(txpacket)

        return result, error

    def write1ByteTxOnly(self, scs_id, address, data):
        data_write = [data]
        return self.writeTxOnly(scs_id, address, 1, data_write)

    def write1ByteTxRx(self, scs_id, address, data):
        data_write = [data]
        return self.writeTxRx(scs_id, address, 1, data_write)

    def write2ByteTxOnly(self, scs_id, address, data):
        data_write = [self.scs_lobyte(data), self.scs_hibyte(data)]
        return self.writeTxOnly(scs_id, address, 2, data_write)

    def write2ByteTxRx(self, scs_id, address, data):
        data_write = [self.scs_lobyte(data), self.scs_hibyte(data)]
        return self.writeTxRx(scs_id, address, 2, data_write)

    def write4ByteTxOnly(self, scs_id, address, data):
        data_write = [self.scs_lobyte(self.scs_loword(data)),
                      self.scs_hibyte(self.scs_loword(data)),
                      self.scs_lobyte(self.scs_hiword(data)),
                      self.scs_hibyte(self.scs_hiword(data))]
        return self.writeTxOnly(scs_id, address, 4, data_write)

    def write4ByteTxRx(self, scs_id, address, data):
        data_write = [self.scs_lobyte(self.scs_loword(data)),
                      self.scs_hibyte(self.scs_loword(data)),
                      self.scs_lobyte(self.scs_hiword(data)),
                      self.scs_hibyte(self.scs_hiword(data))]
        return self.writeTxRx(scs_id, address, 4, data_write)

    def regWriteTxOnly(self, scs_id, address, length, data):
        txpacket = [0] * (length + 7)

        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = length + 3
        txpacket[PKT_INSTRUCTION] = INST_REG_WRITE
        txpacket[PKT_PARAMETER0] = address

        txpacket[PKT_PARAMETER0 + 1: PKT_PARAMETER0 + 1 + length] = data[0: length]

        result = self.txPacket(txpacket)
        self.portHandler.is_using = False

        return result

    def regWriteTxRx(self, scs_id, address, length, data):
        txpacket = [0] * (length + 7)

        txpacket[PKT_ID] = scs_id
        txpacket[PKT_LENGTH] = length + 3
        txpacket[PKT_INSTRUCTION] = INST_REG_WRITE
        txpacket[PKT_PARAMETER0] = address

        txpacket[PKT_PARAMETER0 + 1: PKT_PARAMETER0 + 1 + length] = data[0: length]

        _, result, error = self.txRxPacket(txpacket)

        return result, error

    def syncReadTx(self, start_address, data_length, param, param_length):
        txpacket = [0] * (param_length + 8)
        # 8: HEADER0 HEADER1 ID LEN INST START_ADDR DATA_LEN CHKSUM

        txpacket[PKT_ID] = BROADCAST_ID
        txpacket[PKT_LENGTH] = param_length + 4  # 7: INST START_ADDR DATA_LEN CHKSUM
        txpacket[PKT_INSTRUCTION] = INST_SYNC_READ
        txpacket[PKT_PARAMETER0 + 0] = start_address
        txpacket[PKT_PARAMETER0 + 1] = data_length

        txpacket[PKT_PARAMETER0 + 2: PKT_PARAMETER0 + 2 + param_length] = param[0: param_length]

        # print(txpacket)
        result = self.txPacket(txpacket)
        return result

    def syncReadRx(self, data_length, param_length):
        wait_length = (6 + data_length) * param_length
        self.portHandler.setPacketTimeout(wait_length)
        rxpacket = []
        rx_length = 0
        while True:
            rxpacket.extend(self.portHandler.readPort(wait_length - rx_length))
            rx_length = len(rxpacket)
            if rx_length >= wait_length:
                result = COMM_SUCCESS
                break
            else:
                # check timeout
                if self.portHandler.isPacketTimeout():
                    if rx_length == 0:
                        result = COMM_RX_TIMEOUT
                    else:
                        result = COMM_RX_CORRUPT
                    break
        self.portHandler.is_using = False
        return result, rxpacket

    def syncWriteTxOnly(self, start_address, data_length, param, param_length):
        txpacket = [0] * (param_length + 8)
        # 8: HEADER0 HEADER1 ID LEN INST START_ADDR DATA_LEN ... CHKSUM

        txpacket[PKT_ID] = BROADCAST_ID
        txpacket[PKT_LENGTH] = param_length + 4  # 4: INST START_ADDR DATA_LEN ... CHKSUM
        txpacket[PKT_INSTRUCTION] = INST_SYNC_WRITE
        txpacket[PKT_PARAMETER0 + 0] = start_address
        txpacket[PKT_PARAMETER0 + 1] = data_length

        txpacket[PKT_PARAMETER0 + 2: PKT_PARAMETER0 + 2 + param_length] = param[0: param_length]

        _, result, _ = self.txRxPacket(txpacket)

        return result
