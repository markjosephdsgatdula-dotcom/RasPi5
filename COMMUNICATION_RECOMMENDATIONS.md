# UR10e to Raspberry Pi 5 Communication Guide

This document outlines the alternative communication methods to connect a Universal Robots UR10e arm to a Raspberry Pi 5, bypassing the hardware-level complexity and current-drive issues of the PC817 optocoupler.

---

## Option 1: XML-RPC (Highly Recommended)
XML-RPC is the industry-standard method for interfacing vision sensors and external PCs with Universal Robots. It allows the robot to call Python functions on the Pi over a standard Ethernet network.

### How it Works
1. The Raspberry Pi runs a lightweight Python server.
2. The UR10e PolyScope program registers the Pi's IP address as an XML-RPC factory.
3. The robot calls the camera trigger function synchronously. The robot automatically pauses on that line, waits for the Pi to capture the image, and continues once Python returns `True`.

### Python Server Code (Raspberry Pi 5)
Save this as a service or run it alongside your main script:

```python
from xmlrpc.server import SimpleXMLRPCServer
import os
import time

class RobotCameraInterface:
    def __init__(self):
        # Place references to your camera class or queues here
        self.session_active = True
        self.weld_index = 1
        
    def trigger_capture(self) -> bool:
        """Called by UR10e. Takes a photo, saves it, and returns confirmation."""
        print(f"[XML-RPC] Received capture trigger for weld index {self.weld_index}")
        
        # Insert your OpenCV / Camera capture logic here:
        # success = camera.capture_image(...)
        time.sleep(0.5) # Simulate camera delay
        
        self.weld_index += 1
        return True # Return True to tell the robot the image is saved

    def product_done(self) -> bool:
        """Called by UR10e at the end of a weld cycle."""
        print("[XML-RPC] Product cycle completed. Resetting weld index.")
        self.weld_index = 1
        return True

# Initialize server on Port 8000 (accessible on local network)
server = SimpleXMLRPCServer(("0.0.0.0", 8000), logRequests=False)
interface = RobotCameraInterface()
server.register_instance(interface)

print("XML-RPC Server running on port 8000. Waiting for UR10e...")
server.serve_forever()
```

### URScript Code (UR10e)
In your robot program, you initialize the interface and call the functions directly:

```urscript
# 1. Initialize the client (run once in the startup or installation tab)
camera = xmlrpc("http://192.168.1.189:8000")

# 2. Call the trigger inside your movement loop
# The robot will wait here until the Pi completes the capture
success = camera.trigger_capture()

# 3. Call product completed at the end of the program
camera.product_done()
```

---

## Option 2: Modbus TCP
The UR10e has a built-in Modbus TCP server. The Raspberry Pi can act as a Modbus Client (Master) and read/write I/O registers on the robot over the network.

### How it Works
1. You enable Modbus TCP in the UR10e PolyScope settings.
2. The Python script on the Pi runs a loop polling the state of a virtual digital output register.
3. When the robot sets that register to `1`, the Pi captures the photo and writes it back to `0`.

### Python Client Code (Raspberry Pi 5)
Requires `pyModbusTCP` (`pip install pyModbusTCP`):

```python
from pyModbusTCP.client import ModbusClient
import time

# IP of the UR10e robot controller
UR_IP = "192.168.1.100" 
client = ModbusClient(host=UR_IP, port=502, auto_open=True)

# Register addresses for UR virtual I/Os (consult UR Modbus map)
TRIGGER_REG = 128 # Example virtual output address

print(f"Connecting to UR10e Modbus TCP server at {UR_IP}...")
while True:
    if client.is_open:
        # Read the state of the trigger output register
        trigger_state = client.read_coils(TRIGGER_REG, 1)
        
        if trigger_state and trigger_state[0]:
            print("[MODBUS] Trigger detected!")
            
            # Take photo here...
            # success = camera.capture_image()
            
            # Reset the register to 0 (tell the robot to proceed)
            client.write_single_coil(TRIGGER_REG, False)
            print("[MODBUS] Confirmation sent. Resetting trigger.")
            
    time.sleep(0.05) # 50ms polling loop
```

---

## Option 3: Mechanical Relay Modules (Physical Wires)
If you prefer to keep physical wires but want to bypass the transistor current limit of the PC817:

### Why Relays Work Better:
* Relays use electromagnets to close a physical mechanical switch. 
* There is no forward semiconductor voltage drop ($\sim0.2\text{V} - 1.3\text{V}$) like in transistors, meaning they present a true $0\,\Omega$ resistance when closed.
* Polarity on the switch (contact) side does not matter.

### Hardware Recommendation:
* Purchase a **3.3V Low-Level Trigger Relay Module** (often sold as "Arduino Relay Modules" but specifying 3.3V compatibility).

### Wiring Details:
* **Pi Control Side:**
  * Connect `VCC` -> Pi `3.3V` (Pin 1) or `5V` (Pin 2)
  * Connect `GND` -> Pi `GND` (Pin 9)
  * Connect `IN` -> Pi `GPIO 27` (Pin 13)
* **UR Switch Side:**
  * Connect `COM` (Common) -> UR `24V`
  * Connect `NO` (Normally Open) -> UR `DI4` (Digital Input 4)
