import asyncio
import os
import argparse
from bleak import BleakClient, BleakScanner

# Hide Pygame support prompt
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

# Define motors channels in bytes
drivemotor1 = 0x32
drivemotor2 = 0x33
steeringmotor = 0x34
steeringangletolerance = 5
steeringmaxangle = 0
debug = False
last_power = 0
calibrated = 0

DEVICE_NAME = "Technic Move  "
CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"
#SERVICE_UUID = "00001624-1212-efde-1623-785feabcd123" #todo

currentlysteering = 0
target_angle = 0
stop_event = asyncio.Event()
last_steering_input = None

def calculate_power_byte(power_input):
	return int(power_input + 256 if power_input < 0 else power_input)

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

async def set_drive_motor_power(channel, power_input):
	power_byte = calculate_power_byte(power_input)
	command = bytes([0x08, 0x00, 0x81, channel, 0x11, 0x51, 0x00, power_byte])
	await write_characteristic(CHARACTERISTIC_UUID, command)
	if debug:
		print(f"Sent set_drive_motor_power command to channel {channel}: {command.hex()}")

async def steering_goto_pos(inputangle=None, power=25):
	global currentlysteering, target_angle, last_steering_input, calibrated, steeringmaxangle
	while not stop_event.is_set() and calibrated == 1:
		if inputangle == None:
			angle = target_angle
		else:
			angle = inputangle
			last_steering_input = 0
			target_angle = angle
		# Read data from the characteristic
		if angle == last_steering_input and currentlysteering == 0:
			await asyncio.sleep(0.05)
			continue
		data = await client.read_gatt_char(CHARACTERISTIC_UUID)
		#print(f"Read data: {data.hex()}")		
		if len(data) >= 8 and data[3] == steeringmotor:
			current_angle_bytes = data[4:8]
			current_angle = bytes_to_angle(current_angle_bytes)
			if debug:
				print(f"Current angle: {current_angle}, target angle: {angle}")
			# Check if the current angle is satisfactory
			if abs(current_angle - angle) <= steeringangletolerance:# or ((current_angle <= -steeringmaxangle+steeringangletolerance or current_angle >= steeringmaxangle-steeringangletolerance) and inputangle == None and (angle <= -steeringmaxangle+steeringangletolerance or angle >= steeringmaxangle-steeringangletolerance)):
				command = bytes([0x08, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x00, 0x00])
				await write_characteristic(CHARACTERISTIC_UUID, command)
				currentlysteering = 0
				if debug:
					print("Steering angle is close to target, stopping motor")
				if inputangle != None:
					break
			else:
				#if inputangle == None and abs(angle) >= steeringmaxangle-steeringangletolerance:#apply more power for steering close to maximum position
				#	powermodified = 40
				#	if debug:
				#		print("Applying more power, requested angle: " + str(angle) + ", maxangle: " + str(steeringmaxangle-steeringangletolerance))
				#else:
				#	powermodified = abs(power)
				powermodified = abs(power)
				if current_angle < angle and currentlysteering <= 0:
					command = bytes([0x08, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x00, calculate_power_byte(powermodified)])
					currentlysteering = 1
					await write_characteristic(CHARACTERISTIC_UUID, command)
				elif current_angle > angle and currentlysteering >= 0:
					command = bytes([0x08, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x00, calculate_power_byte(-powermodified)])
					currentlysteering = -1
					await write_characteristic(CHARACTERISTIC_UUID, command)		
		last_steering_input = angle
		await asyncio.sleep(0.05)
		
async def autocalibrate_steering():#0A004134020000000001
	global steeringmaxangle, calibrated, target_angle, last_steering_input
	calibrated = 0
	print("===================================================")
	print("Autocalibration started, PLEASE WAIT...")
	print("It calibrates best when tires don't touch the")
	print("ground, but it will need battery level correction")
	print("anyway.")
	await asyncio.sleep(3.0)
	#subscribe to steering motor angle changes
	command = bytes([0x0A, 0x00, 0x41, steeringmotor, 0x02, 0x00, 0x00, 0x00, 0x00, 0x01])
	await write_characteristic(CHARACTERISTIC_UUID, command)
	#go right at 35% for 1.0s
	command = bytes([0x08, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x00, calculate_power_byte(20)])
	await write_characteristic(CHARACTERISTIC_UUID, command)
	await asyncio.sleep(1.5)
	command = bytes([0x08, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x00, 0x00])
	await write_characteristic(CHARACTERISTIC_UUID, command)
	await asyncio.sleep(0.3)
	#reset encoder
	command = bytes([0x0b, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x02, 0x00, 0x00, 0x00, 0x00])
	await write_characteristic(CHARACTERISTIC_UUID, command)
	await asyncio.sleep(0.3)
	#go left at 35% for 1.5s
	command = bytes([0x08, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x00, calculate_power_byte(-20)])
	await write_characteristic(CHARACTERISTIC_UUID, command)
	await asyncio.sleep(1.5)
	command = bytes([0x08, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x00, 0x00])
	await write_characteristic(CHARACTERISTIC_UUID, command)
	await asyncio.sleep(0.3)
	#calculate total move degrees - get position, which which is equal to -total movement range
	data = await read_characteristic(CHARACTERISTIC_UUID)
	steeringrange = -(bytes_to_angle(data[4:8]))
	if debug:
		print("Steering range: " + str(steeringrange) + " deg.")
	#goto centered angle
	tempcenteredangle = -(int(steeringrange/2))
	calibrated = 1
	await steering_goto_pos(tempcenteredangle, 20)
	await asyncio.sleep(0.5)	
	#reset encoder
	command = bytes([0x0b, 0x00, 0x81, steeringmotor, 0x11, 0x51, 0x02, 0x00, 0x00, 0x00, 0x00])
	await write_characteristic(CHARACTERISTIC_UUID, command)
	await asyncio.sleep(0.3)
	steeringmaxangle = int(steeringrange/2)
	#print("steeringmaxangle set to: ", steeringmaxangle)
	target_angle = 0
	last_steering_input = 0
	await asyncio.sleep(0.6)
	print("Autocalibration FINISHED. You can drive now!")
	print("===================================================")
	#0b00813411510200000000 reset encoder

async def connect_to_device(name):
	global client
	devices = await BleakScanner.discover()
	for device in devices:
		if device.name == name:
			client = BleakClient(device.address)
			await client.connect()
			return client
	return None

async def read_characteristic(characteristic_uuid):
	data = await client.read_gatt_char(characteristic_uuid)
	return data

async def write_characteristic(characteristic_uuid, data):
	await client.write_gatt_char(characteristic_uuid, data)

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
			if port == steeringmotor and len(data) == 8:#for our script, we assume we're getting steering angle here
				angle = data[4:8]
				angle = bytes_to_angle(angle)
				buffer = buffer + " angle: " + str(angle) + "deg"
	print(f"Read data: {data.hex()} {buffer}")

async def request_hub_properties(characteristic_uuid):
	await asyncio.sleep(0.3)
	await write_characteristic(characteristic_uuid, bytes.fromhex("0500010305"))
	fw_data = await read_characteristic(characteristic_uuid)
	firmware_version = process_hub_property_data(fw_data)

	await asyncio.sleep(0.3)
	await write_characteristic(characteristic_uuid, bytes.fromhex("0500010405"))
	hw_data = await read_characteristic(characteristic_uuid)
	hardware_version = process_hub_property_data(hw_data)

	await asyncio.sleep(0.3)
	await write_characteristic(characteristic_uuid, bytes.fromhex("0500010605"))
	battery_data = await read_characteristic(characteristic_uuid)
	battery_percentage = process_hub_property_data(battery_data)
	
	await asyncio.sleep(0.3)
	await write_characteristic(characteristic_uuid, bytes.fromhex("0800813F11510006"))#change hub led color to green, so we're sure we're in control
	
	await asyncio.sleep(3.0)
	await write_characteristic(characteristic_uuid, bytes.fromhex("09008135115100ff00"))#turn off 6led so we won't waste battery for now (led mask, power int 0-100)

	return firmware_version, hardware_version, battery_percentage

async def handle_controller_events():
	global power_input, last_power, target_angle, last_steering_input
	powerchanged = False
	steeringchanged = False
	for event in pygame.event.get():
		if event.type == pygame.JOYAXISMOTION:
			left_trigger = joystick.get_axis(4)
			right_trigger = joystick.get_axis(5)
			power_input = int(((-left_trigger + right_trigger) * 100) / 2)
			if abs(power_input) < 20:
				power_input = 0
			if abs(power_input - last_power) >= 5:
				powerchanged = True
				last_power = power_input
				await asyncio.create_task(set_drive_motor_power(drivemotor1, -power_input))
				await asyncio.create_task(set_drive_motor_power(drivemotor2, power_input))
			input_angle = int(joystick.get_axis(0)*steeringmaxangle)
			if abs(input_angle - last_steering_input) >= steeringangletolerance:
				steeringchanged = True
				target_angle = input_angle
			if ((powerchanged or steeringchanged) and debug):
				print(f"power_input: {power_input}, steering_input: {target_angle}")
async def read_input():
	loop = asyncio.get_event_loop()
	while True:
		command = await loop.run_in_executor(None, input, "Enter data to write or type 'read' / 'exit' or use controller:\n")
		yield command.strip().lower()

async def handle_terminal_commands(stop_event):
	current_characteristic_uuid = CHARACTERISTIC_UUID
	async for cmd in read_input():
		if cmd == "exit":
			stop_event.set()
			break
		elif cmd == "read":
			data = await read_characteristic(current_characteristic_uuid)
			process_read_data(data)
		else:
			try:
				data_bytes = bytes.fromhex(cmd)
				await write_characteristic(current_characteristic_uuid, data_bytes)
				print("Data written")
				if debug:
					data = await read_characteristic(current_characteristic_uuid)
					process_read_data(data)
			except ValueError:
				print("Invalid hex data format")

async def main():
	global joystick
	print("Searching for LEGO Porsche car. Make sure it's on and blinking...")

	client = await connect_to_device(DEVICE_NAME)
	if client is None:
		print(f"Device '{DEVICE_NAME}' not found.")
		return

	await client.pair()
	firmware_version, hardware_version, battery_percentage = await request_hub_properties(CHARACTERISTIC_UUID)
	print(f"Connected to {DEVICE_NAME}")
	print(f"Firmware Version: {firmware_version}")
	print(f"Hardware Version: {hardware_version}")
	print(f"Battery level: {battery_percentage}%")

	pygame.init()
	pygame.joystick.init()
	
	if pygame.joystick.get_count() == 0:
		print("No joystick found")

	else:
		joystick = pygame.joystick.Joystick(0)
		joystick.init()	
		print(f"Joystick name: {joystick.get_name()}")
	
	await autocalibrate_steering()

	try:
		await asyncio.gather(
			handle_terminal_commands(stop_event),
			controller_event_loop(stop_event),
			asyncio.create_task(steering_goto_pos())
		)
	except KeyboardInterrupt:
		pass
	
	#unsubscribe to steering motor angle changes
	command = bytes([0x0A, 0x00, 0x41, steeringmotor, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00])
	await write_characteristic(CHARACTERISTIC_UUID, command)
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
	args = parser.parse_args()
	debug = args.debug
	asyncio.run(main())
