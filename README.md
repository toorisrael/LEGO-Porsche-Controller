# LEGO-Porsche-Controller
Python tool made to control LEGO Porsche 42176 with XBox Controller and PC

For now, it supports:
- reading joystick input with pygame
- connecting to LEGO's new Technic Move hub introduced in set 42176 with bleak
- reading and writing Bluetooth Low Energy data to vehicle
- reading battery level, HW and FW version
- driving forward and backwards using XBox Controller
- steering right / left

I'm currently working on:
- joystick selection if required
- checking battery level any time
- telemetry

Usage:
```
python lego-porsche-controller.py
Searching for LEGO Porsche car. Make sure it's on and blinking...
Debug mode is: OFF
Connected to Technic Move
Firmware Version: 1.6.5.0
Hardware Version: 0.3.0.0
Battery level: 56%
Battery voltage: 3.653V
HUB temperature: 27.8C
Calibrating steering...
Car is READY!
Power is UNLIMITED
Joystick name: Xbox Series X Controller
Enter data to write, use controller or type 'help':
```
Commandline
```
-debug           Enables debug mode
-power x         Limits max drive power to value between 25% and 100% (for kids)
```
Commands
```
00000000         Write any specified bytes to bluetooth LWP3 characteristic
read             Read data from LWP3 characteristic
autocalibrate    Recalibrate steering
debug            Prints if debug mode is enabled or not
voltage          Prints battery voltage
temp             Prints HUB temperature
debugon          Enable debug mode
debugoff         Disable debug mode
joystick         Initialize joystick (usefull if joy disconnected or not connected on start)
power x          Limits max drive power to value between 25% and 100% (for kids)
angletobytes     Convert int angle to bytes representation used by gopos commands
bytestoangle     Convert angle bytes to int angle
help             Show all available commands
```

Add -debug to print sending commands and controller inputs

Sources used for creating this project:

[Pybricks](https://github.com/pybricks/)

[SharpBrick.PoweredUp](https://github.com/sharpbrick/powered-up)

[brickcontroller2](https://github.com/imurvai/brickcontroller2/)

[bleak](https://github.com/hbldh/bleak)

[pygame](https://github.com/pygame)

[LWP3 documentation](https://lego.github.io/lego-ble-wireless-protocol-docs/)

[TechnicMoveHub](https://github.com/DanieleBenedettelli/TechnicMoveHub/)
