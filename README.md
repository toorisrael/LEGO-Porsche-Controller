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
- 6LED switch
- stall protection
- joystick selection if required
- checking battery level any time

Usage:
```
python lego-porsche-controller.py
Searching for LEGO Porsche car. Make sure it's on and blinking...
Connected to Technic Move
Firmware Version: 1.6.5.0
Hardware Version: 0.3.0.0
Battery level: 36%
Joystick name: Xbox Series X Controller
Enter data to write or type 'read' / 'exit' or use controller:
exit

Disconnected
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
