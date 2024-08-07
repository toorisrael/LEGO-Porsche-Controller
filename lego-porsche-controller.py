import asyncio
import os
import argparse
from bleak import BleakClient, BleakScanner

# Hide Pygame support prompt
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

# Define channels in bytes
drivemotor1 = 0x32
drivemotor2 = 0x33
steeringmotor = 0x34
leds = 0x35
playvm = 0x36
hubled = 0x3F
LIGHTS_ON_ON = 0
LIGHTS_ON_BRAKING = 1
LIGHTS_OFF_OFF = 4
LIGHTS_OFF_BRAKING = 5

# Globals
client = None
debug = False
joystick = None
last_power_input = 0
last_steering_input = 0
stop_event = asyncio.Event()
powerlimit = 100
brakeapplied = False
lightsplayvmstate = LIGHTS_OFF_OFF
last_lights_input = False

DEVICE_NAME = "Technic Move  "
CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"
#SERVICE_UUID = "00001624-1212-efde-1623-785feabcd123"

def normalize_angle(angle):
	if angle >= 180:
		return angle - (360 * ((angle + 180) // 360))
	elif angle < -180:
		return angle + (360 * ((180 - angle) // 360))
	return angle

def angle_to_bytes(angle):
	a0 = angle & 0xff
	a1 = (angle >> 8) & 0xff
	a2 = (angle >> 16) & 0xff
	a3 = (angle >> 24) & 0xff
	return a0, a1, a2, a3

def bytes_to_angle(byte_array):
	if len(byte_array) != 4:
		raise ValueError("Byte array must be exactly 4 bytes long.")
	angle = (byte_array[3] << 24) | (byte_array[2] << 16) | (byte_array[1] << 8) | byte_array[0]
	
	# Handle negative values (32-bit signed integer)
	if angle >= 0x80000000:
		angle -= 0x100000000	
	return angle

async def set_drive_motor_power(channel, power_byte):
	command = bytes([0x08, 0x00, 0x81, channel, 0x11, 0x51, 0x00, power_byte])
	await write_characteristic(command)
	if debug:
		print(f"Sent set_drive_motor_power command to channel {channel}: {command.hex()}")

async def connect_to_device(name):
	global client
	devices = await BleakScanner.discover()
	for device in devices:
		if device.name == name:
			client = BleakClient(device.address)
			await client.connect()
			return client
	return None

async def read_characteristic():
	data = await client.read_gatt_char(CHARACTERISTIC_UUID)
	return data

async def write_characteristic(data):
	try:
		await client.write_gatt_char(CHARACTERISTIC_UUID, data)	
	except Exception as e:
		print(f"Failed to write data  {data.hex()}: {e}")
	else:
		if debug:
			print(f"{data.hex()} written")

def process_hub_property_data(data):
	if data is None or len(data) < 6:
		return None

	data_length = data[0]
	message_id = data[2]
	property_id = data[3]
	property_operation = data[4]

	if message_id != 0x01 or property_operation != 0x06:
		return None

	if property_id == 0x03:  # FW version
		return process_version_number(data, 5)
	elif property_id == 0x04:  # HW version
		return process_version_number(data, 5)
	elif property_id == 0x06:  # Battery voltage
		return str(data[5])
	return None

def process_version_number(data, index):
	if len(data) < index + 4:
		return ''

	v0 = data[index]
	v1 = data[index + 1]
	v2 = data[index + 2]
	v3 = data[index + 3]

	major = v3 >> 4
	minor = v3 & 0xf
	bugfix = ((v2 >> 4) * 10) + (v2 & 0xf)
	build = ((v1 >> 4) * 1000) + ((v1 & 0xf) * 100) + ((v0 >> 4) * 10) + (v0 & 0xf)

	return f"{major}.{minor}.{bugfix}.{build}"

def process_read_data(data):
	buffer = ""
	if len(data) >= 5:
		data_length = data[0]
		message_type = data[2]
		if message_type == 0x05:
			buffer = buffer + "[Error]"
			commandtype = data[3]
			errortype = data[4]
			if commandtype == 0x81:
				buffer = buffer + " Port Output Command"                
				if errortype == 0x05:
					buffer = buffer + "->Command NOT recognized"
				elif errortype == 0x06:
					buffer = buffer + "->Invalid use (e.g. parameter error(s))"
			elif commandtype == 0x41:
				buffer = buffer + " Port Input Command" 
				if errortype == 0x05:
					buffer = buffer + "->Command NOT recognized"
				elif errortype == 0x06:
					buffer = buffer + "->Invalid use (e.g. parameter error(s))"
			elif commandtype == 0x00:
				buffer = buffer + " Generic (wrong size??)"
		elif message_type == 0x82:        
			port = data[3]
			status = data[4]
			buffer = buffer + "[Port Output Command Feedback] Port " + str(int(port))
			if status == 0x0a:
				buffer = buffer + " OK"
			else:
				buffer = buffer + " ??"
		elif message_type == 0x45:
			port = data[3]
			buffer = buffer + "[Port Input subscribed data] Port " + str(int(port))
			if port == steeringmotor and len(data) == 8:# For our script, we assume we're getting steering angle here
				angle = data[4:8]
				angle = bytes_to_angle(angle)
				buffer = buffer + " angle: " + str(angle) + "deg"
		elif message_type == 0x47:
			port = data[3]
			buffer = buffer + "[Port Input subscribtion changed] Port " + str(int(port))
	print(f"Read data: {data.hex()} {buffer}")

async def initialize_hub():
	await write_characteristic(bytes.fromhex("0500010305"))
	fw_data = await read_characteristic()
	firmware_version = process_hub_property_data(fw_data)

	await write_characteristic(bytes.fromhex("0500010405"))
	hw_data = await read_characteristic()
	hardware_version = process_hub_property_data(hw_data)

	await write_characteristic(bytes.fromhex("0500010605"))
	battery_data = await read_characteristic()
	battery_percentage = process_hub_property_data(battery_data)
	
	# Change hub led color to green, so we're sure we're in control
	await asyncio.sleep(1.0)
	await write_characteristic(bytes.fromhex("0800813F11510006"))
	
	print(f"Connected to {DEVICE_NAME}")
	print(f"Firmware Version: {firmware_version}")
	print(f"Hardware Version: {hardware_version}")
	print(f"Battery level: {battery_percentage}%\n")	
	await autocalibrate_steering()
	power_limit()

	# Turn off 6led so we won't waste battery for now (led mask, power int 0-100) - this needs to be delayed, as the leds blink after connection first few seconds
	await write_characteristic(bytes.fromhex("09008135115100ff00"))

async def initialize_joystick():
	global joystick
	pygame.joystick.init()
	
	if pygame.joystick.get_count() == 0:
		print("No joystick found.")#todo joystick reinitialization and selection in separate function with available command
	else:
		joystick = pygame.joystick.Joystick(0)
		joystick.init()	
		print(f"Joystick name: {joystick.get_name()}")

async def autocalibrate_steering():
	print("Calibrating steering...")
	await write_characteristic(bytes.fromhex("0d008136115100030000001000"))
	await write_characteristic(bytes.fromhex("0d008136115100030000000800"))
	await asyncio.sleep(1.5)
	print("Car is READY!")

async def handle_controller_events():
	global last_power_input, last_steering_input, powerlimit, lightsplayvmstate, brakeapplied, last_lights_input
	for event in pygame.event.get():
		if event.type == pygame.JOYAXISMOTION or event.type == pygame.JOYBUTTONDOWN or event.type == pygame.JOYBUTTONUP:
			
			# drive power
			power_input = int(((joystick.get_axis(5)-joystick.get_axis(4)) * 100) / 2)
			power_input_modified = int(power_input*(powerlimit*0.01))
			if abs(power_input_modified) <= 15:
				power_input_modified = 0
			elif power_input_modified >= 95:
				power_input_modified = 100
			elif power_input_modified <= -95:
				power_input_modified = -100
			
			# steering
			steering_input = int(joystick.get_axis(0)*100)
			steering_input_modified = steering_input
			if abs(steering_input_modified) <= 2:
				steering_input_modified = 0
			elif steering_input_modified >= 95:
				steering_input_modified = 100
			elif steering_input_modified <= -95:
				steering_input_modified = -100

			# braking
			brake_state_changed = False
			brake_input = joystick.get_button(5)
			if brake_input and not brakeapplied:
				brake_state_changed = True
				brakeapplied = True				
			elif not brake_input and brakeapplied:
				brake_state_changed = True
				brakeapplied = False

			# lights on/off
			lights_state_changed = False
			lights_input = 0
			lights_input = joystick.get_button(3)
			if event.type == pygame.JOYBUTTONDOWN:				
				if lights_input and not last_lights_input:
					if debug:
						print("lights_input and not last_lights_input")
					lights_state_changed = True
					last_lights_input = True
					if lightsplayvmstate == LIGHTS_ON_ON or lightsplayvmstate == LIGHTS_ON_BRAKING:
						lightsplayvmstate = LIGHTS_OFF_OFF
						if debug:
							print("Lights changed from LIGHTS_ON_ON to LIGHTS_OFF_OFF")						
					elif lightsplayvmstate == LIGHTS_OFF_OFF or lightsplayvmstate == LIGHTS_OFF_BRAKING:
						lights_state_changed = True
						lightsplayvmstate = LIGHTS_ON_ON
						if debug:
							print("Lights changed from LIGHTS_OFF_OFF to LIGHTS_ON_ON")
			if event.type == pygame.JOYBUTTONUP and last_lights_input:
				last_lights_input = False

			if debug:
				print(f"power_input: {power_input} (modified: {power_input_modified}), steering_input: {steering_input} (modified: {steering_input_modified}), brake_input: {brake_input}, lights_input: {lights_input}")

			# Ignore power_input change for less than 5% and steering less than 3%
			power_input_changed = False
			steering_input_changed = False
			if abs(power_input_modified - last_power_input) >= 5:
				power_input_changed = True
				last_power_input = power_input_modified
			if abs(steering_input_modified - last_steering_input):
				steering_input_changed = True
				last_steering_input = steering_input_modified

			if brake_input:
				if lightsplayvmstate == LIGHTS_OFF_OFF:
					lights = LIGHTS_OFF_BRAKING
				elif lightsplayvmstate == LIGHTS_ON_ON:
					lights = LIGHTS_ON_BRAKING
			else: 
				lights = lightsplayvmstate
			# Send PLAYVM commands
			if (power_input_changed or steering_input_changed or brake_state_changed or lights_state_changed) and client != None and client.is_connected:		
				command = bytes([0x0d, 0x00, 0x81, 0x36, 0x11, 0x51, 0x00, 0x03, 0x00, 0x00, steering_input_modified&0xFF, lights, 0x00])
				await write_characteristic(command)
				# Send drive motor power commands directly to get instant response
				if not brake_input:
					await set_drive_motor_power(drivemotor1, -power_input_modified&0xFF)
					await set_drive_motor_power(drivemotor2, power_input_modified&0xFF)
				else: # engine braking
					await set_drive_motor_power(drivemotor1, 0x7F)
					await set_drive_motor_power(drivemotor2, 0x7F)
				# todo those can be send in one command
				
				
			elif debug:
				print("Drive commands ignored due to low input change or HUB disconnected!")
				
				
async def read_input():
	loop = asyncio.get_event_loop()
	while True:
		command = await loop.run_in_executor(None, input, "Enter data to write, use controller or type 'help':\n")
		yield command.strip().lower()

def debug_mode(status=None):
	global debug
	if status != None:
		debug = status
	print("Debug mode is:", "ON" if debug else "OFF")

def power_limit(limit=None):
	global powerlimit
	if limit != None:
		if limit and 25 <= limit <= 100:
			powerlimit = limit
		else:
			print("Power limit must be between 25 and 100")
	print(f"Power limited to {powerlimit}%")

async def handle_terminal_commands(stop_event):
	global powerlimit
	async for cmd in read_input():
		parts = cmd.split()  # Rozdziela komendę od argumentów
		command = parts[0]
		if command == "exit":
			stop_event.set()
			break
		elif command == "read":
			data = await read_characteristic()
			process_read_data(data)
		elif command == "debug":
			debug_mode()
		elif command == "debugon":
			debug_mode(True)
		elif command == "debugoff":
			debug_mode(False)
		elif command == "autocalibrate":
			await autocalibrate_steering()
		elif command == "joystick":
			await initialize_joystick()
		elif command == "power":
			if len(parts) == 2 and parts[1].isdigit():
				limit = int(parts[1])
				power_limit(limit)
			else:
				print("Invalid power limit command. Usage: powerlimit <value>")
		elif command == "help":
			print("Available commands: exit, read, debug, debugon, debugoff, autocalibrate, joystick, help, power")
		else:
			try:
				data_bytes = bytes.fromhex(command)  # Zakładamy, że komenda to mogą być dane hex
				await write_characteristic(data_bytes)
				print("Data written")
				if debug:
					data = await read_characteristic()
					process_read_data(data)
			except ValueError:
				print("Invalid hex data format or unknown command")


async def main():
	global client, joystick
	print("Searching for LEGO Porsche car. Make sure it's on and blinking...")
	debug_mode()
	client = await connect_to_device(DEVICE_NAME)
	if client is None:
		print(f"Device '{DEVICE_NAME}' not found.")
		return

	await client.pair(protection_level = 2)
	await initialize_hub()

	pygame.init()
	await initialize_joystick()
	
	try:
		await asyncio.gather(
			handle_terminal_commands(stop_event),
			controller_event_loop(stop_event)
		)
	except KeyboardInterrupt:
		pass
	
	await client.disconnect()
	print("Disconnected")

async def controller_event_loop(stop_event):
	try:
		while not stop_event.is_set():
			await handle_controller_events()
			await asyncio.sleep(0.05)
	except KeyboardInterrupt:
		pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LEGO Porsche Controller")
    parser.add_argument('-debug', action='store_true', help="Enable debug mode to print controller inputs")
    parser.add_argument('-power', type=int, choices=range(25, 101), help="Set initial power limit (25-100)")
    args = parser.parse_args()

    debug = args.debug
    if args.power is not None:
        powerlimit = args.power

    asyncio.run(main())

#todo telemetry
#todo remember 6leds state for drive with playvm command
#todo brake