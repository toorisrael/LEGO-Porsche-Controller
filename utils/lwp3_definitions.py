
# Definitions

DEVICE_NAME = "Technic Move  "
CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123" #LWP3
SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123"

# Define channels
PORT_DRIVE_MOTOR_1 = 0x32
PORT_DRIVE_MOTOR_2 = 0x33
PORT_STEERING_MOTOR = 0x34
PORT_6LEDS = 0x35
PORT_PLAYVM = 0x36
PORT_TEMPERATURE = 0x37
PORT_ACCELEROMETER = 0x38
PORT_GYRO = 0x39
PORT_TILT = 0x3A
PORT_ORIENTATION = 0x3B
PORT_VOLTAGE = 0x3C
PORT_UNKNOWN_1 = 0x3D
PORT_GEST = 0x3E
PORT_HUB_LED = 0x3F

# Define PLAYVM commands
PLAYVM_LIGHTS_ON_ON = 0x00
PLAYVM_LIGHTS_ON_BRAKING = 0x01
PLAYVM_LIGHTS_OFF_OFF = 0x04
PLAYVM_LIGHTS_OFF_BRAKING = 0x05
PLAYVM_CALIBRATE_STEERING = 0x08
PLAYVM_COMMAND = 0x10

# Define HUB LED colors
HUB_LED_MODE_COLOR = 0x00
HUB_LED_MODE_RGB = 0x01
HUB_LED_COLOR_NONE = 0x00
HUB_LED_COLOR_MAGENTA = 0x02
HUB_LED_COLOR_BLUE = 0x03
HUB_LED_COLOR_GREEN = 0x06
HUB_LED_COLOR_YELLOW = 0x07
HUB_LED_COLOR_ORANGE = 0x08
HUB_LED_COLOR_RED = 0x09

# Define HUB properties
HUB_PROPERTY = 0x01
HUB_PROPERTY_NAME = 0x01
HUB_PROPERTY_BUTTON = 0x02
HUB_PROPERTY_FW = 0x03
HUB_PROPERTY_HW = 0x04
HUB_PROPERTY_RSSI = 0x05
HUB_PROPERTY_BATTERY_LEVEL = 0x06
HUB_PROPERTY_BATTERY_TYPE = 0x07
HUB_PROPERTY_MANUFACTURER = 0x08
HUB_PROPERTY_RADIO_FW = 0x09
HUB_PROPERTY_LWP = 0x0A
HUB_PROPERTY_SYSTEM_TYPE = 0x0B
HUB_PROPERTY_HW_NETWORK = 0x0C
HUB_PROPERTY_MAC_1 = 0x0D
HUB_PROPERTY_MAC_2 = 0x0E
HUB_PROPERTY_HW_NETWORK = 0x0F

HUB_PROPERTY_OPERATION_REQUEST_UPDATE = 0x05
HUB_PROPERTY_OPERATION_UPDATE = 0x06 #received

# Commands
MESSAGE_HEADER = 0x00
MESSAGE_TYPE_ERROR = 0x05
MESSAGE_TYPE_PORT_VALUE = 0x45
MESSAGE_TYPE_PORT_OUTPUT_COMMAND_FEEDBACK = 0x82

PORT_INPUT_INFORMATION_REQUEST = 0x21
PORT_INPUT_COMMAND = 0x41
PORT_OUTPUT_COMMAND = 0x81
PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT = 0x51

PORT_MODE_0 = 0x00
PORT_MODE_1 = 0x01
PORT_MODE_2 = 0x02
PORT_MODE_3 = 0x03
PORT_MODE_4 = 0x04

FEEDBACK_ACTION_NO_ACTION = 0x00
FEEDBACK_ACTION_ACTION_COMPLETION = 0x01
FEEDBACK_ACTION_ACTION_START = 0x10
FEEDBACK_ACTION_BOTH = 0x11

# Errors
ERROR_GENERIC = 0x00
ERROR_COMMAND_NOT_RECOGNIZED = 0x05
ERROR_INVALID_USE = 0x06