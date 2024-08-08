import asyncio
import os
import argparse
from utils.lwp3_definitions import *
from bleak import BleakClient, BleakScanner
from struct import unpack

# Hide Pygame support prompt
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

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
cabinlights = False
last_cabin_lights_input = False

def create_command(*args):
	command = bytes([len(args) + 2] + [MESSAGE_HEADER] + list(args))
	return command

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
	return bytes([a0, a1, a2, a3])

def bytes_to_angle(byte_array):
	if len(byte_array) != 4:
		raise ValueError("Byte array must be exactly 4 bytes long.")
	angle = (byte_array[3] << 24) | (byte_array[2] << 16) | (byte_array[1] << 8) | byte_array[0]
	
	# Handle negative values (32-bit signed integer)
	if angle >= 0x80000000:
		angle -= 0x100000000	
	return angle

def is_integer(s):
	if s[0] == '-':
		return s[1:].isdigit()
	return s.isdigit()

async def set_drive_motor_power(channel, power_byte):
	command = create_command(PORT_OUTPUT_COMMAND, channel, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, PORT_MODE_0, power_byte)
	await write_characteristic(command)
	if debug:
		print(f"Sent set_drive_motor_power command to channel {channel}: {command.hex()}")

async def reset_encoder(channel):
	await write_characteristic(create_command(PORT_OUTPUT_COMMAND, channel, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, PORT_MODE_2, 0x00, 0x00, 0x00, 0x00)) # angle bytes for 0 degrees

def get_led_mask(led_states):
	if len(led_states) != 6:
		raise ValueError("There must be exactly 6 LED states provided.")
	
	mask = 0
	for index, state in enumerate(led_states):
		if state:
			mask |= (1 << index)
	return mask

#async def go_pos(channel, byte_array): # this is wrong
#	command = bytes([0x0b, 0x00, 0x81, channel, 0x11, 0x51, 0x03, byte_array[0], byte_array[1]])
#	await write_characteristic(command)

async def connect_to_device(name, max_attempts=10):
	global client
	attempt = 0
	while attempt < max_attempts:
		attempt += 1
		if debug:
			print(f"Connection attempt {attempt}/{max_attempts}")
		devices = await BleakScanner.discover(timeout=3)
		for device in devices:
			if device.name == name:
				client = BleakClient(device.address)
				try:
					await client.connect()
					return client
				except Exception as e:
					print(f"Failed to connect: {e}")
		if debug:
			print("Device not found, retrying...")
		await asyncio.sleep(1)  # optional: delay before next attempt
	print("Failed to connect after maximum attempts.")
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

	message_id = data[2]
	property_id = data[3]
	property_operation = data[4]

	if message_id != HUB_PROPERTY or property_operation != HUB_PROPERTY_OPERATION_UPDATE:
		return None

	if property_id == HUB_PROPERTY_FW:
		return process_version_number(data, 5)
	elif property_id == HUB_PROPERTY_HW:
		return process_version_number(data, 5)
	elif property_id == HUB_PROPERTY_BATTERY_LEVEL:
		return str(data[5])
	elif property_id == HUB_PROPERTY_LWP:
		return process_lwp_version_number(data, 5)
	return None

def process_voltage_or_temperature(data):
	if len(data) != 2:
		return 0
	# unpack unsigned short little-endian
	value = unpack('<H', data[:2])[0]
	return value

async def get_battery_info():
	await write_characteristic(create_command(PORT_INPUT_INFORMATION_REQUEST, PORT_VOLTAGE, FEEDBACK_ACTION_NO_ACTION, 0x01, 0x00)) # port mode? updates count? mode combinations?
	data = await read_characteristic()
	battery_voltage = process_voltage_or_temperature(data[4:6])/1000

	await write_characteristic(create_command(HUB_PROPERTY, HUB_PROPERTY_BATTERY_LEVEL, HUB_PROPERTY_OPERATION_REQUEST_UPDATE))
	battery_level = await read_characteristic()
	battery_level = process_hub_property_data(battery_level)
	
	print(f"Battery voltage: {battery_voltage:.3f}V [{battery_level}%]")

async def get_temperature():
	await write_characteristic(create_command(PORT_INPUT_INFORMATION_REQUEST, PORT_TEMPERATURE, FEEDBACK_ACTION_NO_ACTION, 0x01, 0x00))
	data = await read_characteristic()
	hub_temperature = process_voltage_or_temperature(data[4:6])/10
	
	print(f"HUB temperature: {hub_temperature:.1f}C")	

def process_version_number(data, index):
	if len(data) < index + 4:
		return ''

	v0, v1, v2, v3 = unpack('>BBBB', data[index:index + 4])

	major = v3 >> 4
	minor = v3 & 0xf
	bugfix = ((v2 >> 4) * 10) + (v2 & 0xf)
	build = ((v1 >> 4) * 1000) + ((v1 & 0xf) * 100) + ((v0 >> 4) * 10) + (v0 & 0xf)

	return f"{major}.{minor}.{bugfix}.{build}"

def process_lwp_version_number(data, index):
	if len(data) < index + 2:
		return ''

	version_number = unpack('>H', data[index:index + 2])[0]

	major = (version_number >> 12) * 1000 + ((version_number >> 8) & 0xF) * 100 + ((version_number >> 4) & 0xF) * 10 + (version_number & 0xF)
	minor = ((version_number >> 4) & 0xF) * 10 + (version_number & 0xF)

	return f"{major}.{minor}"

def process_read_data(data):
	buffer = ""
	if len(data) >= 5:
		data_length = data[0]
		message_type = data[2]
		if message_type == MESSAGE_TYPE_ERROR:
			buffer = buffer + "[Error]"
			commandtype = data[3]
			errortype = data[4]
			if commandtype == PORT_OUTPUT_COMMAND:
				buffer = buffer + " Port Output Command"                
				if errortype == ERROR_COMMAND_NOT_RECOGNIZED:
					buffer = buffer + "->Command NOT recognized"
				elif errortype == ERROR_INVALID_USE:
					buffer = buffer + "->Invalid use (e.g. parameter error(s))"
			elif commandtype == PORT_INPUT_COMMAND:
				buffer = buffer + " Port Input Command" 
				if errortype == ERROR_COMMAND_NOT_RECOGNIZED:
					buffer = buffer + "->Command NOT recognized"
				elif errortype == ERROR_INVALID_USE:
					buffer = buffer + "->Invalid use (e.g. parameter error(s))"
			elif commandtype == ERROR_GENERIC:
				buffer = buffer + " Generic (wrong size??)"
		elif message_type == MESSAGE_TYPE_PORT_OUTPUT_COMMAND_FEEDBACK:        
			port = data[3]
			status = data[4]
			buffer = buffer + "[Port Output Command Feedback] Port " + str(int(port))
			if status == 0x0a:
				buffer = buffer + " OK"
			else:
				buffer = buffer + " ??"
		elif message_type == MESSAGE_TYPE_PORT_VALUE:
			port = data[3]
			buffer = buffer + "[Port Value] Port " + str(int(port))
			if port == PORT_STEERING_MOTOR and len(data) == 8:# For our script, we assume we're getting steering angle here
				angle = data[4:8]
				angle = bytes_to_angle(angle)
				buffer = buffer + " angle: " + str(angle) + "deg"
			if port == PORT_TEMPERATURE:
				databytes = data[4:6]
				value = process_voltage_or_temperature(databytes)/10
				buffer = buffer + " temperature bytes: " + str(databytes.hex()) + f" [{value:.1f}C]"
			if port == PORT_VOLTAGE:
				databytes = data[4:6]
				value = process_voltage_or_temperature(databytes)/1000
				buffer = buffer + " voltage bytes: " + str(databytes.hex()) + f" [{value:.3f}V]"
		elif message_type == 0x47:
			port = data[3]
			buffer = buffer + "[Port Input subscribtion changed] Port " + str(int(port))
	print(f"Read data: {data.hex()} {buffer}")

async def initialize_hub():
	await write_characteristic(create_command(HUB_PROPERTY, HUB_PROPERTY_FW, HUB_PROPERTY_OPERATION_REQUEST_UPDATE))
	fw_data = await read_characteristic()
	firmware_version = process_hub_property_data(fw_data)

	await write_characteristic(create_command(HUB_PROPERTY, HUB_PROPERTY_HW, HUB_PROPERTY_OPERATION_REQUEST_UPDATE))
	hw_data = await read_characteristic()
	hardware_version = process_hub_property_data(hw_data)

	await write_characteristic(create_command(HUB_PROPERTY, HUB_PROPERTY_LWP, HUB_PROPERTY_OPERATION_REQUEST_UPDATE))
	lwp_data = await read_characteristic()
	lwp_version = process_hub_property_data(lwp_data)

	# Change hub led color to green, so we're sure we're in control
	await asyncio.sleep(1.0)
	await write_characteristic(create_command(PORT_OUTPUT_COMMAND, PORT_HUB_LED, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, HUB_LED_MODE_COLOR, HUB_LED_COLOR_GREEN))
	
	print(f"Connected to {DEVICE_NAME}")
	print(f"Firmware Version: {firmware_version}")
	print(f"Hardware Version: {hardware_version}")
	print(f"LWP Version: {lwp_version}")
	await get_battery_info()
	await get_temperature()
	await autocalibrate_steering()
	power_limit()

	# Turn off 6led so we won't waste battery for now (led mask, power int 0-100)
	#await write_characteristic(create_command(PORT_OUTPUT_COMMAND, PORT_6LEDS, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, PORT_MODE_0, 0xff, 0x00))
	await write_characteristic(create_command(PORT_OUTPUT_COMMAND, PORT_PLAYVM, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, PORT_MODE_0, 0x03, 0x00, 0x00, 0x00, LIGHTS_OFF_OFF, 0x00))

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
	# "Special" PLAYVM commands to calibrate steering
	await write_characteristic(create_command(PORT_OUTPUT_COMMAND, PORT_PLAYVM, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, PORT_MODE_0, 0x03, 0x00, 0x00, 0x00, 0x10, 0x00))
	await write_characteristic(create_command(PORT_OUTPUT_COMMAND, PORT_PLAYVM, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, PORT_MODE_0, 0x03, 0x00, 0x00, 0x00, 0x08, 0x00))
	print("Car is READY!")

async def handle_controller_events():
	global last_power_input, last_steering_input, powerlimit, lightsplayvmstate, brakeapplied, last_lights_input, cabinlights, last_cabin_lights_input
	for event in pygame.event.get():
		if event.type == pygame.JOYAXISMOTION or event.type == pygame.JOYBUTTONDOWN:
			
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
			# Prevent triggering overcurrent protection at max steering input - calibration by PLAYVM is not super precise
			# limiting to 94% is enough to prevent overcurrent, 88 should be good to prevent stall
			# todo: adjust joystick input to get linear 0-88%
			elif steering_input_modified >= 88:
				steering_input_modified = 88
			elif steering_input_modified <= -88:
				steering_input_modified = -88

			# braking
			brake_state_changed = False
			brake_input = joystick.get_button(5)
			if brake_input and not brakeapplied:
				brake_state_changed = True
				brakeapplied = True				
			elif not brake_input and brakeapplied:
				brake_state_changed = True
				brakeapplied = False

			# cabin lights on/off
			cabin_lights_input = joystick.get_button(1)
			if event.type == pygame.JOYBUTTONDOWN:				
				if cabin_lights_input and not last_cabin_lights_input:
					if debug:
						print("cabin_lights_input and not last_cabin_lights_input")
					last_cabin_lights_input = True
					if cabinlights == True:
						cabinlights = False
						if debug:
							print("Cabin lights changed from True to False")						
					else:
						cabinlights = True
						if debug:
							print("Cabin lights changed from False to True")
					cabinlightsbyte = 100 if cabinlights else 0
					await write_characteristic(create_command(PORT_OUTPUT_COMMAND, PORT_6LEDS, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, PORT_MODE_0, get_led_mask([1, 0, 0, 1, 0, 0]), cabinlightsbyte))
			if event.type == pygame.JOYBUTTONUP and last_cabin_lights_input:
				last_cabin_lights_input = False

			# lights on/off
			lights_state_changed = False
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
			if abs(steering_input_modified - last_steering_input) >= 3:
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
				await write_characteristic(create_command(PORT_OUTPUT_COMMAND, PORT_PLAYVM, FEEDBACK_ACTION_BOTH, PORT_OUTPUT_SUBCOMMAND_WRITE_DIRECT, PORT_MODE_0, 0x03, 0x00, 0x00, steering_input_modified&0xFF, lights, 0x00))
				# Send drive motor power commands directly to get instant response
				if not brake_input:
					await set_drive_motor_power(PORT_DRIVE_MOTOR_1, -power_input_modified&0xFF)
					await set_drive_motor_power(PORT_DRIVE_MOTOR_2, power_input_modified&0xFF)
				else: # engine braking # todo don't send when only lights or steering changed
					await set_drive_motor_power(PORT_DRIVE_MOTOR_1, 0x7F)
					await set_drive_motor_power(PORT_DRIVE_MOTOR_2, 0x7F)
				# todo those can be send in one command maybe?				
			elif debug:
				print("Drive commands ignored due to low input change or HUB disconnected!")
		elif event.type == pygame.JOYBUTTONUP:
			last_cabin_lights_input = joystick.get_button(1)
			last_lights_input = joystick.get_button(3)

				
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
	if powerlimit != 100:
		print(f"Power limited to {powerlimit}%")
	else:
		print(f"Power is UNLIMITED")

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
		elif command == "voltage":
			await get_battery_info()
		elif command == "temp":
			await get_temperature()
		elif command == "power":
			if len(parts) == 2 and parts[1].isdigit():
				limit = int(parts[1])
				power_limit(limit)
			elif len(parts) == 1:
				power_limit()
			else:
				print("Invalid power limit command. Usage: powerlimit <value>")
		elif command == "getledmask":
			if len(parts) == 7 and all(part.isdigit() for part in parts[1:]):
				led_states = [bool(int(arg)) for arg in parts[1:]]
				mask = get_led_mask(led_states)
				print(f"Generated LED mask: {mask:02x}")
			else:
				print("Invalid getledmask command. Usage example: getledmask 0 0 1 0 0 0")
		elif command == "angletobytes":
			if len(parts) == 2 and is_integer(parts[1]):
				angle = int(parts[1])
				anglebytes = angle_to_bytes(angle)
				print(f"Angle {angle} bytes representation: {anglebytes.hex()}")
			else:
				print("Invalid angletobytes command. Usage: angletobytes angle (int)")
		elif command == "bytestoangle":
			if len(parts) == 2:
				try:
					anglebytes = parts[1]
					angle = bytes_to_angle(bytes.fromhex(anglebytes))
					print(f"Angle bytes {anglebytes} int representation: {angle}")
				except ValueError:
					print("Invalid hex data format.")
					print("Invalid bytestoangle command. Usage: bytestoangle angle (hex)")
			else:
				print("Invalid bytestoangle command. Usage: bytestoangle angle (hex)")
		elif command == "help":			
			print("Available commands: angletobytes, autocalibrate, bytestoangle, debug, debugoff, debugon, exit, getledmask, help, joystick, power, read, temp, voltage")
			print("'read' is automatically called after any write in debug-mode")
		else:
			try:
				data_bytes = bytes.fromhex(command)
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
#todo fix stalling drive motor on low power and fast steering inputs + drive direction changes