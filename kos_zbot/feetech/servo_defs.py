BROADCAST_ID = 0xFE  # 254
MAX_ID = 0xFC  # 252
SCS_END = 0

# Instruction for SCS Protocol
INST_PING = 1
INST_READ = 2
INST_WRITE = 3
INST_REG_WRITE = 4
INST_ACTION = 5
INST_SYNC_WRITE = 131  # 0x83
INST_SYNC_READ = 130  # 0x82

# Communication Result
COMM_SUCCESS = 0  # tx or rx packet communication success
COMM_PORT_BUSY = -1  # Port is busy (in use)
COMM_TX_FAIL = -2  # Failed transmit instruction packet
COMM_RX_FAIL = -3  # Failed get status packet
COMM_TX_ERROR = -4  # Incorrect instruction packet
COMM_RX_WAITING = -5  # Now recieving status packet
COMM_RX_TIMEOUT = -6  # There is no status packet
COMM_RX_CORRUPT = -7  # Incorrect status packet
COMM_NOT_AVAILABLE = -9  #


# Protocol Error bit
ERRBIT_VOLTAGE = 1
ERRBIT_ANGLE = 2
ERRBIT_OVERHEAT = 4
ERRBIT_OVERELE = 8
ERRBIT_OVERLOAD = 32


#-----Baud Rate-----
SMS_STS_1M = 0
SMS_STS_0_5M = 1
SMS_STS_250K = 2
SMS_STS_128K = 3
SMS_STS_115200 = 4
SMS_STS_76800 = 5
SMS_STS_57600 = 6
SMS_STS_38400 = 7

#-------EEPROM --------
SMS_STS_MODEL_L = 3
SMS_STS_MODEL_H = 4

#-------EEPROM --------
SMS_STS_ID = 5
SMS_STS_BAUD_RATE = 6
SMS_STS_MIN_ANGLE_LIMIT_L = 9
SMS_STS_MIN_ANGLE_LIMIT_H = 10
SMS_STS_MAX_ANGLE_LIMIT_L = 11
SMS_STS_MAX_ANGLE_LIMIT_H = 12
SMS_STS_KP = 21  # Speed loop P gain
SMS_STS_KD = 22  # Speed loop D gain

#-------SRAM --------
SMS_STS_CW_DEAD = 26
SMS_STS_CCW_DEAD = 27
SMS_STS_OFS_L = 31
SMS_STS_OFS_H = 32
SMS_STS_MODE = 33

#-------SRAM --------
SMS_STS_TORQUE_ENABLE = 40
SMS_STS_ACC = 41
SMS_STS_GOAL_POSITION_L = 42
SMS_STS_GOAL_POSITION_H = 43
SMS_STS_GOAL_TIME_L = 44
SMS_STS_GOAL_TIME_H = 45
SMS_STS_GOAL_SPEED_L = 46
SMS_STS_GOAL_SPEED_H = 47
SMS_STS_LOCK = 55

#-------SRAM --------
SMS_STS_PRESENT_POSITION_L = 56
SMS_STS_PRESENT_POSITION_H = 57
SMS_STS_PRESENT_SPEED_L = 58
SMS_STS_PRESENT_SPEED_H = 59
SMS_STS_PRESENT_LOAD_L = 60
SMS_STS_PRESENT_LOAD_H = 61
SMS_STS_PRESENT_VOLTAGE = 62
SMS_STS_PRESENT_TEMPERATURE = 63
SMS_STS_MOVING = 66
SMS_STS_PRESENT_CURRENT_L = 69
SMS_STS_PRESENT_CURRENT_H = 70

#Factory Settings
SMS_STS_DEFAULT_MOVING_THRESHOLD = 80
SMS_STS_DEFAULT_DTS_MS = 81
SMS_STS_DEFAULT_VK_MS = 82
SMS_STS_DEFAULT_VMIN = 83
SMS_STS_DEFAULT_VMAX = 84
SMS_STS_DEFAULT_AMAX = 85
SMS_STS_DEFAULT_KACC = 86


servoRegs = [
    {"name": "Model", "addr": SMS_STS_MODEL_L, "size": 2, "type": "uint16"},
    {"name": "ID", "addr": SMS_STS_ID, "size": 1, "type": "uint8"},
    {"name": "Baudrate", "addr": SMS_STS_BAUD_RATE, "size": 1, "type": "uint8"},
    {"name": "Return Delay", "addr": 7, "size": 1, "type": "uint8"},
    {"name": "Response Status Level", "addr": 8, "size": 1, "type": "uint8"},
    {
        "name": "Min Angle Limit",
        "addr": SMS_STS_MIN_ANGLE_LIMIT_L,
        "size": 2,
        "type": "uint16",
    },
    {
        "name": "Max Angle Limit",
        "addr": SMS_STS_MAX_ANGLE_LIMIT_L,
        "size": 2,
        "type": "uint16",
    },
    {"name": "Max Temperature Limit", "addr": 13, "size": 1, "type": "uint8"},
    {"name": "Max Voltage Limit", "addr": 14, "size": 1, "type": "uint8"},
    {"name": "Min Voltage Limit", "addr": 15, "size": 1, "type": "uint8"},
    {"name": "Max Torque Limit", "addr": 16, "size": 2, "type": "uint16"},
    {"name": "Phase", "addr": 18, "size": 1, "type": "uint8"},
    {"name": "Unloading Condition", "addr": 19, "size": 1, "type": "uint8"},
    {"name": "LED Alarm Condition", "addr": 20, "size": 1, "type": "uint8"},
    {"name": "P Coefficient", "addr": 21, "size": 1, "type": "uint8"},
    {"name": "D Coefficient", "addr": 22, "size": 1, "type": "uint8"},
    {"name": "I Coefficient", "addr": 23, "size": 1, "type": "uint8"},
    {"name": "Minimum Startup Force", "addr": 24, "size": 2, "type": "uint16"},
    {"name": "CW Dead Zone", "addr": SMS_STS_CW_DEAD, "size": 1, "type": "uint8"},
    {"name": "CCW Dead Zone", "addr": SMS_STS_CCW_DEAD, "size": 1, "type": "uint8"},
    {"name": "Protection Current", "addr": 28, "size": 2, "type": "uint16"},
    {"name": "Angular Resolution", "addr": 30, "size": 1, "type": "uint8"},
    {"name": "Offset", "addr": SMS_STS_OFS_L, "size": 2, "type": "uint16"},
    {"name": "Mode", "addr": SMS_STS_MODE, "size": 1, "type": "uint8"},
    {"name": "Protective Torque", "addr": 34, "size": 1, "type": "uint8"},
    {"name": "Protection Time", "addr": 35, "size": 1, "type": "uint8"},
    {"name": "Overload Torque", "addr": 36, "size": 1, "type": "uint8"},
    {
        "name": "Speed closed loop P proportional coefficient",
        "addr": 37,
        "size": 1,
        "type": "uint8",
    },
    {"name": "Over Current Protection Time", "addr": 38, "size": 1, "type": "uint8"},
    {
        "name": "Velocity closed loop I integral coefficient",
        "addr": 39,
        "size": 1,
        "type": "uint8",
    },
    {
        "name": "Torque Enable",
        "addr": SMS_STS_TORQUE_ENABLE,
        "size": 1,
        "type": "uint8",
    },
    {"name": "Acceleration", "addr": SMS_STS_ACC, "size": 1, "type": "uint8"},
    {
        "name": "Goal Position",
        "addr": SMS_STS_GOAL_POSITION_L,
        "size": 2,
        "type": "uint16",
    },
    {"name": "Goal Time", "addr": SMS_STS_GOAL_TIME_L, "size": 2, "type": "uint16"},
    {"name": "Goal Speed", "addr": SMS_STS_GOAL_SPEED_L, "size": 2, "type": "int16"},
    {"name": "Lock", "addr": SMS_STS_LOCK, "size": 1, "type": "uint8"},
    {
        "name": "Present Position",
        "addr": SMS_STS_PRESENT_POSITION_L,
        "size": 2,
        "type": "uint16",
    },
    {
        "name": "Present Speed",
        "addr": SMS_STS_PRESENT_SPEED_L,
        "size": 2,
        "type": "int16",
    },
    {
        "name": "Present Load",
        "addr": SMS_STS_PRESENT_LOAD_L,
        "size": 2,
        "type": "int16",
    },
    {
        "name": "Present Voltage",
        "addr": SMS_STS_PRESENT_VOLTAGE,
        "size": 1,
        "type": "uint8",
    },
    {
        "name": "Present Temperature",
        "addr": SMS_STS_PRESENT_TEMPERATURE,
        "size": 1,
        "type": "uint8",
    },
    {"name": "Status", "addr": 65, "size": 1, "type": "uint8"},
    {"name": "Moving", "addr": SMS_STS_MOVING, "size": 1, "type": "uint8"},
    {
        "name": "Present Current",
        "addr": SMS_STS_PRESENT_CURRENT_L,
        "size": 2,
        "type": "uint16",
    },
    {
        "name": "Default Moving Threshold",
        "addr": SMS_STS_DEFAULT_MOVING_THRESHOLD,
        "size": 1,
        "type": "uint8",
    },
    {"name": "Default DTS", "addr": SMS_STS_DEFAULT_DTS_MS, "size": 1, "type": "uint8"},
    {"name": "Default VK", "addr": SMS_STS_DEFAULT_VK_MS, "size": 1, "type": "uint8"},
    {"name": "Default VMIN", "addr": SMS_STS_DEFAULT_VMIN, "size": 1, "type": "uint8"},
    {"name": "Default VMAX", "addr": SMS_STS_DEFAULT_VMAX, "size": 1, "type": "uint8"},
    {"name": "Default AMAX", "addr": SMS_STS_DEFAULT_AMAX, "size": 1, "type": "uint8"},
    {"name": "Default KACC", "addr": SMS_STS_DEFAULT_KACC, "size": 1, "type": "uint8"},
]