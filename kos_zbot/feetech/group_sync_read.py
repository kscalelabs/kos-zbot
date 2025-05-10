#!/usr/bin/env python

from .scservo_def import *
import time

class GroupSyncRead:
    def __init__(self, ph, start_address, data_length):
        self.ph = ph
        self.start_address = start_address
        self.data_length = data_length

        self.last_result = False
        self.is_param_changed = False
        self.param = []
        self.data_dict = {}
        self.stamp_dict   = {}   # id → last‑ok monotonic time (s)
        self.max_age_s    = 0.05 # accept data that is ≤50 ms old

        self.clearParam()

    def makeParam(self):
        if not self.data_dict:  # len(self.data_dict.keys()) == 0:
            return

        self.param = []

        for scs_id in self.data_dict:
            self.param.append(scs_id)

    def addParam(self, scs_id):
        if scs_id in self.data_dict:  # scs_id already exist
            return False

        self.data_dict[scs_id] = []  # [0] * self.data_length

        self.is_param_changed = True
        return True

    def removeParam(self, scs_id):
        if scs_id not in self.data_dict:  # NOT exist
            return

        del self.data_dict[scs_id]

        self.is_param_changed = True

    def clearParam(self):
        self.data_dict.clear()

    def txPacket(self):
        if not self.data_dict:

            return COMM_NOT_AVAILABLE

        if self.is_param_changed is True or not self.param:
            self.makeParam()
            self.is_param_changed = False

        return self.ph.syncReadTx(self.start_address, self.data_length, self.param, len(self.data_dict.keys()))

    def rxPacket(self):
        self.last_result = True

        result = COMM_RX_FAIL

        if len(self.data_dict.keys()) == 0:
            return COMM_NOT_AVAILABLE

        result, rxpacket = self.ph.syncReadRx(self.data_length, len(self.data_dict.keys()))
        # print(rxpacket)
        if len(rxpacket) >= (self.data_length+6):
            for scs_id in self.data_dict:
                frame, result = self.readRx(rxpacket, scs_id, self.data_length)
                if result == COMM_SUCCESS and frame:
                    self.data_dict[scs_id]  = frame
                    self.stamp_dict[scs_id] = time.monotonic()
                else:
                    self.last_result = False         # keep old data, just flag error
        else:
            self.last_result = False
        # print(self.last_result)
        return result

    def txRxPacket(self):
        result = self.txPacket()
        if result != COMM_SUCCESS:
            return result

        return self.rxPacket()

    def readRx(self, rxpacket, scs_id, data_length):
        # print(scs_id)
        # print(rxpacket)
        data = []
        rx_length = len(rxpacket)
        # print(rx_length)
        rx_index = 0;
        while (rx_index+6+data_length) <= rx_length:
            headpacket = [0x00, 0x00, 0x00]
            while rx_index < rx_length:
                headpacket[2] = headpacket[1];
                headpacket[1] = headpacket[0];
                headpacket[0] = rxpacket[rx_index];
                rx_index += 1
                if (headpacket[2] == 0xFF) and (headpacket[1] == 0xFF) and headpacket[0] == scs_id:
                    # print(rx_index)
                    break
            # print(rx_index+3+data_length)
            if (rx_index+3+data_length) > rx_length:
                break;
            if rxpacket[rx_index] != (data_length+2):
                rx_index += 1
                # print(rx_index)
                continue
            rx_index += 1
            Error = rxpacket[rx_index]
            rx_index += 1
            calSum = scs_id + (data_length+2) + Error
            data = [Error]
            data.extend(rxpacket[rx_index : rx_index+data_length])
            for i in range(0, data_length):
                calSum += rxpacket[rx_index]
                rx_index += 1
            calSum = ~calSum & 0xFF
            # print(calSum)
            if calSum != rxpacket[rx_index]:
                return None, COMM_RX_CORRUPT
            return data, COMM_SUCCESS 
        # print(rx_index)
        return None, COMM_RX_CORRUPT

    def isAvailable(self, scs_id, address, data_length):
        # quick structural checks
        if (scs_id not in self.data_dict or
            address < self.start_address or
            address + data_length > self.start_address + self.data_length or
            len(self.data_dict[scs_id]) < data_length + 1):
            return False, 0

        # age test
        age = time.monotonic() - self.stamp_dict.get(scs_id, 0)
        if age > self.max_age_s:
            return False, 0

        return True, self.data_dict[scs_id][0]

    def getData(self, scs_id, address, data_length):
        if data_length == 1:
            return self.data_dict[scs_id][address-self.start_address+1]
        elif data_length == 2:
            return self.ph.scs_makeword(self.data_dict[scs_id][address-self.start_address+1],
                                self.data_dict[scs_id][address-self.start_address+2])
        elif data_length == 4:
            return self.ph.scs_makedword(self.ph.scs_makeword(self.data_dict[scs_id][address-self.start_address+1],
                                              self.data_dict[scs_id][address-self.start_address+2]),
                                 self.ph.scs_makeword(self.data_dict[scs_id][address-self.start_address+3],
                                              self.data_dict[scs_id][address-self.start_address+4]))
        else:
            return 0
