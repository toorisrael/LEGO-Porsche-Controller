import asyncio
import os
import argparse
from bleak import BleakClient, BleakScanner

# Hide Pygame support prompt
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

# Define engine channels in bytes
engine1 = 0x32  # Byte value for the first engine channel
engine2 = 0x33  # Byte value for the second engine channel
debug = False
last_power = 0

DEVICE_NAME = "Technic Move  "
CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"

def calculate_power_byte(power_input):
    return int(power_input + 256 if power_input < 0 else power_input)

async def send_motor_command(client, engine_channel, power_input):
    power_byte = calculate_power_byte(power_input)
    command = bytes([0x08, 0x00, 0x81, engine_channel, 0x11, 0x51, 0x00, power_byte])
    await write_characteristic(client, CHARACTERISTIC_UUID, command)
    if debug:
        print(f"Sent motor command to channel {engine_channel}: {command.hex()}")



async def connect_to_device(name):
    global client
    devices = await BleakScanner.discover()
    for device in devices:
        if device.name == name:
            client = BleakClient(device.address)
            await client.connect()
            return client
    return None

async def read_characteristic(client, characteristic_uuid):
    data = await client.read_gatt_char(characteristic_uuid)
    return data

async def write_characteristic(client, characteristic_uuid, data):
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

async def request_hub_properties(client, characteristic_uuid):
    await asyncio.sleep(0.3)
    await write_characteristic(client, characteristic_uuid, bytes.fromhex("0500010305"))
    fw_data = await read_characteristic(client, characteristic_uuid)
    firmware_version = process_hub_property_data(fw_data)

    await asyncio.sleep(0.3)
    await write_characteristic(client, characteristic_uuid, bytes.fromhex("0500010405"))
    hw_data = await read_characteristic(client, characteristic_uuid)
    hardware_version = process_hub_property_data(hw_data)

    await asyncio.sleep(0.3)
    await write_characteristic(client, characteristic_uuid, bytes.fromhex("0500010605"))
    battery_data = await read_characteristic(client, characteristic_uuid)
    battery_percentage = process_hub_property_data(battery_data)
    
    await asyncio.sleep(0.3)
    await write_characteristic(client, characteristic_uuid, bytes.fromhex("0800813F11510002"))#change led color to green, so we're sure we're in control

    return firmware_version, hardware_version, battery_percentage

def handle_controller_events(client):
    global debug, power_input, last_power
    for event in pygame.event.get():
        if event.type == pygame.JOYAXISMOTION:
            left_trigger = joystick.get_axis(4)
            right_trigger = joystick.get_axis(5)
            power_input = ((-left_trigger + right_trigger) * 100) / 2
            if debug:
                print(f"power_input: {power_input:.2f}")
            if abs(power_input) < 20:
                power_input = 0
            if abs(power_input - last_power) > 5:
                last_power = power_input
                asyncio.create_task(send_motor_command(client, engine1, -power_input))
                asyncio.create_task(send_motor_command(client, engine2, power_input))

async def read_input():
    loop = asyncio.get_event_loop()
    while True:
        command = await loop.run_in_executor(None, input, "Enter data to write or type 'read' / 'exit' or use controller:\n")
        yield command.strip().lower()

async def handle_terminal_commands(client, stop_event):
    global debug
    current_characteristic_uuid = CHARACTERISTIC_UUID
    async for cmd in read_input():
        if cmd == "exit":
            stop_event.set()
            break
        elif cmd == "read":
            data = await read_characteristic(client, current_characteristic_uuid)
            print(f"Read data: {data.hex()}")
        else:
            try:
                data_bytes = bytes.fromhex(cmd)
                await write_characteristic(client, current_characteristic_uuid, data_bytes)
                print("Data written")
                if debug:
                    data = await read_characteristic(client, current_characteristic_uuid)
                    print(f"Read data: {data.hex()}")
            except ValueError:
                print("Invalid hex data format")

async def main():
    global joystick, client
    print("Searching for LEGO Porsche car. Make sure it's on and blinking...")

    client = await connect_to_device(DEVICE_NAME)
    if client is None:
        print(f"Device '{DEVICE_NAME}' not found.")
        return

    await client.pair()
    firmware_version, hardware_version, battery_percentage = await request_hub_properties(client, CHARACTERISTIC_UUID)
    print(f"Connected to {DEVICE_NAME}")
    print(f"Firmware Version: {firmware_version}")
    print(f"Hardware Version: {hardware_version}")
    print(f"Battery level: {battery_percentage}%")

    pygame.init()
    pygame.joystick.init()
    
    if pygame.joystick.get_count() == 0:
        print("No joystick found")
        await client.disconnect()
        return
    
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    print(f"Joystick name: {joystick.get_name()}")

    stop_event = asyncio.Event()
    
    try:
        await asyncio.gather(
            handle_terminal_commands(client, stop_event),
            controller_event_loop(stop_event)
        )
    except KeyboardInterrupt:
        pass

    await client.disconnect()
    print("Disconnected")

async def controller_event_loop(stop_event):
    try:
        while not stop_event.is_set():
            handle_controller_events(client)
            await asyncio.sleep(0.05)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LEGO Porsche Controller")
    parser.add_argument('-debug', action='store_true', help="Enable debug mode to print controller inputs")
    args = parser.parse_args()
    debug = args.debug
    asyncio.run(main())
