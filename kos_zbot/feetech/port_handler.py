#!/usr/bin/env python

import time
import serial
import sys
import platform

#TODO: clean this up
DEFAULT_BAUDRATE = 1000000
# Assume 50Hz
LATENCY_TIMER_US = 40      # 40 µs  → 0.04 ms
MAX_BUSY_US      = 8_000   # 8 us   hard cap
MIN_TIMEOUT_US   = 1_000   # 1 us   floor

class PortHandler(object):
    def __init__(self, port_name):
        self.is_open = False
        self.baudrate = DEFAULT_BAUDRATE
        self.packet_start_time = 0.0
        self.packet_timeout = 0.0
        self.tx_time_per_byte = 0.0

        self.is_using = False
        self.port_name = port_name
        self.ser = None

    def openPort(self):
        return self.setBaudRate(self.baudrate)

    def closePort(self):
        self.ser.close()
        self.is_open = False

    def clearPort(self):
        self.ser.flush()

    def setPortName(self, port_name):
        self.port_name = port_name

    def getPortName(self):
        return self.port_name

    def setBaudRate(self, baudrate):
        baud = self.getCFlagBaud(baudrate)

        if baud <= 0:
            # self.setupPort(38400)
            # self.baudrate = baudrate
            return False  # TODO: setCustomBaudrate(baudrate)
        else:
            self.baudrate = baudrate
            return self.setupPort(baud)

    def getBaudRate(self):
        return self.baudrate

    def getBytesAvailable(self):
        return self.ser.in_waiting

    def readPort(self, length):
        if (sys.version_info > (3, 0)):
            return self.ser.read(length)
        else:
            return [ord(ch) for ch in self.ser.read(length)]

    def writePort(self, packet):
        return self.ser.write(packet)


    def setPacketTimeout(self, expected_bytes: int, extra_us: int = 0) -> None:
        """
        expected_bytes : bytes still to arrive on the wire
                        (caller already added header etc.)
        Stores the deadline in micro‑seconds so it matches getCurrentTime_us().
        """
        self.packet_start_time = self.getCurrentTime_us()

        bit_time_us  = 1_000_000.0 / self.baudrate     # e.g. 2.0 µs @ 500 kBd
        calc_timeout = expected_bytes * 10.0 * bit_time_us   # 10 bits/byte
        calc_timeout += LATENCY_TIMER_US                       # USB latency
        # clamp into sane range
        if calc_timeout < MIN_TIMEOUT_US:
            calc_timeout = MIN_TIMEOUT_US
        elif calc_timeout > MAX_BUSY_US:
            calc_timeout = MAX_BUSY_US

        calc_timeout += extra_us
        self.packet_timeout = calc_timeout              # ***micro‑seconds***

    def isPacketTimeout(self):
        if self.getTimeSinceStart() > self.packet_timeout:
            self.packet_timeout = 0
            return True

        return False

    def getTimeSinceStart(self):
        time_since = self.getCurrentTime_us() - self.packet_start_time
        if time_since < 0.0:
            self.packet_start_time = self.getCurrentTime_us()

        return time_since

    def getCurrentTime_us(self):
        # monotonic, microseconds
        return time.monotonic_ns() / 1_000.0


    def setupPort(self, cflag_baud):
        if self.is_open:
            self.closePort()

        self.ser = serial.Serial(
            port=self.port_name,
            baudrate=self.baudrate,
            # parity = serial.PARITY_ODD,
            # stopbits = serial.STOPBITS_TWO,
            bytesize=serial.EIGHTBITS,
            timeout=0
        )

        self.is_open = True

        self.ser.reset_input_buffer()
        self.tx_time_per_byte = (1000.0 / self.baudrate) * 10.0

        return True

    def getCFlagBaud(self, baudrate):
        if baudrate in [4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 250000, 500000, 1000000]:
            return baudrate
        else:
            return -1          