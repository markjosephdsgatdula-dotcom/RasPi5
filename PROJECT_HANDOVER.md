# Weld Inspection System Handover

This document contains everything needed to resume this project on a different PC. You can open a new chat with an AI coding assistant (like Gemini or Claude) at work, upload/paste this document, and they will be fully up to speed instantly.

---

## 1. Project Overview
A Raspberry Pi 5 system connected to a monochrome USB camera and a Universal Robots UR10e arm. It captures weld inspection photos on hardware triggers, organizes them automatically by product and weld point, and displays a live monitoring dashboard.

### Directory Structure
```
weld_inspection_system/
├── .gitignore             # Ignores .env and local data/ images
├── .env.example           # Example config for Pi connection
├── .env                  # Local Pi credentials (do not commit!)
├── requirements.txt       # Project python packages
├── deploy_script.py       # SFTP transfer & remote launcher
├── main.py                # Main app & session state management
├── README.md              # Original readme file
└── src/
    ├── __init__.py
    ├── camera_capture.py  # OpenCV capture & vertical orientation flip
    ├── trigger_handler.py # gpiozero listening for robot signals
    └── ui_app.py          # CustomTkinter dashboard GUI
```

---

## 2. GPIO Pinout & Wiring

The UR10e operates at **24V digital I/O**, whereas the Raspberry Pi 5 operates at **3.3V**. We are using a **PC817 Optocoupler module** to isolate and step down the signals safely.

| Signal Name | Source → Destination | BCM Pin on Pi | Behavior / Timing |
| :--- | :--- | :--- | :--- |
| **Capture trigger** | UR10e → Pi | **BCM 17** | Input. When HIGH (24V active), takes photo. Debounced at 250ms. |
| **Capture confirm** | Pi → UR10e | **BCM 27** | Output. Sends a **100ms HIGH pulse** back to robot after image is safely written to disk. |
| **Product done** | UR10e → Pi | **BCM 22** | Input. Signals that a product is finished, advancing the product count and resetting the weld index to 1. |

*Note: The PC817 module does not invert the signals (HIGH input = HIGH output).*

---

## 3. How to Run & Test

### On your PC (For development / UI preview)
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   python main.py
   ```
   *Note: It will show warnings that GPIO and the camera cannot be initialized (since you are on a PC), but the GUI will open and function normally for layout checks.*

### Deploying & Running on the Pi 5
1. Make sure your PC is connected to the same network as the Pi.
2. Edit the `.env` file on your PC to set the Pi's IP, username, and password.
3. Run the deployment script from your PC's terminal:
   ```bash
   python deploy_script.py
   ```
   This script automatically uploads the code to the Pi and runs it on the Pi's screen.

---

## 4. Current Progress Status

* **Phase 1 (Done & Verified):** Core UI dashboard, live video capture with vertical flip, image directory auto-creation, and local deploy script are fully working.
* **Phase 2 (Code Complete, Awaiting Physical Testing):**
  - **Auto-resuming Session:** Counters (product # and weld index) are saved to `session_state.json` on the Pi on every trigger. If the Pi reboots, it reads this file and resumes exactly where it left off.
  - **Dynamic Folder Routing:** Weld point directories (e.g. `weldpoint_01/`, `weldpoint_02/`) are created on the fly during the first run. All subsequent product runs save images into their respective folders (e.g., `product_002.jpg` goes into `weldpoint_01/`).
* **Next Task:** Perform physical loopback testing of the GPIO inputs on the Pi (shorting BCM 17/22 to 3.3V) and wire the optocoupler to the UR10e.

---

## 5. Conversation Context for the AI Assistant

**Copy and paste the prompt below into your next chat session to resume:**

```text
Hi! I want to resume work on my Robotic Weld Inspection System project. 
Here is the summary of what we have done:
- We built a Python app that runs on a Raspberry Pi 5.
- It interfaces with a monochrome USB camera at /dev/video1 (requires vertical flip: cv2.flip(gray, 0)) and a UR10e Robot Arm via GPIO pins (BCM 17: trigger, BCM 27: confirm output, BCM 22: product done).
- The folder structure automatically groups images of the same weld point together:
  data/captured_images/{product_name}/weldpoint_{weld_index:02d}/product_{product_num:03d}_{timestamp}.jpg
- It saves its session state in `session_state.json` after every trigger so that if it reboots, it resumes the exact product/weld counts.
- We have a `deploy_script.py` that connects via SFTP using paramiko to deploy code to the Pi (IP: 192.168.11.35, user: rinkamarkmaaku) and launches main.py on DISPLAY=:0.
- All code has been pushed to a GitHub repository at: https://github.com/markjosephdsgatdula-dotcom/Ras-PI-5-program.git

Please review the codebase, help me set up my local environment, and let's get ready to test the GPIO trigger signals.
```
