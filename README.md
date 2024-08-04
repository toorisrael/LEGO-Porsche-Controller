# LEGO-Porsche-Controller
Python tool made to control LEGO Porsche 42176 with XBox Controller and PC

For now, it supports:
- reading joystick input with pygame
- connecting to LEGO's new Technic Move hub introduced in set 42176 with bleak
- reading and writing Bluetooth Low Energy data to vehicle
- reading battery level, HW and FW version
- driving forward and backwards using XBox Controller

I'm currently working on:
- steering funcionality
- 6LED funcionality
- stall protection
- joystick selection if required

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
