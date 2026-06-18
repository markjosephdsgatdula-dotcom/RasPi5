# Weld Inspection System Handover

This document contains everything needed to resume this project on a different PC (e.g. at work). You can open a new chat with an AI coding assistant (like Gemini or Claude) at work, upload/paste this document, and they will be fully up to speed instantly.

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
    ├── camera_capture.py  # OpenCV capture with dynamic open/close states
    ├── trigger_handler.py # gpiozero listening for robot signals (with PC mock fallback)
    └── ui_app.py          # CustomTkinter dashboard GUI with Tabview (Live Monitor & Gallery)
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
   pip install customtkinter pillow paramiko opencv-python
   ```
2. Run the app:
   ```bash
   python main.py
   ```
   *Note: It will show warnings that GPIO and the camera cannot be initialized (since you are on a PC), but the GUI will open and function normally in simulation/preview mode. You can toggle the camera (Open/Close) and simulate robot triggers manually.*

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

* **Phase 1 (Done & Verified):** Core UI dashboard, live video capture with vertical flip, image directory auto-creation, local deploy script are fully working.
* **Phase 2 (Completed & Deployed):**
  - **Tabbed Dashboard**: Re-built the UI with a `ctk.CTkTabview` containing:
    - **Live Monitor**: Displays live camera feed, a scrolling console log, and a canvas-drawn camera connection status LED (Green for connected, Red for closed/disconnected). Includes manual debugging override buttons to simulate robot triggers.
    - **Inspection Gallery**: Scans `data/captured_images/` dynamically. The user can select a product lot and weld point to browse captured runs side-by-side using "Next" and "Previous" buttons.
  - **Dynamic Camera Controls**: Added UI toggles to open/close the camera. Closing the camera releases the `/dev/video1` device resource so other applications can use it.
  - **Refactored Queue Architecture**: Implemented a double-queue structure (`ui_to_main_queue` and `main_to_ui_queue`) to eliminate event peeking, race conditions, and CPU spinning.
  - **Local Simulation**: Integrated try-except fallbacks for `gpiozero` so developers can test layouts on PCs.
* **Current Task**: Collect training images using the system, transfer them to a PC, and prepare to implement an automatic labeling script using Meta's **MobileSAM** model to bypass manual polygon annotations.

---

## 5. Conversation Context for the AI Assistant

**Copy and paste the prompt below into your next chat session to resume:**

```text
Hi! I want to resume work on my Robotic Weld Inspection System project. 
Here is the summary of what we have done:
- We built a Python app that runs on a Raspberry Pi 5.
- It interfaces with a monochrome USB camera at /dev/video1 (requires vertical flip: cv2.flip(gray, 0)) and a UR10e Robot Arm via GPIO pins (BCM 17: trigger, BCM 27: confirm output, BCM 22: product done).
- We implemented a tabbed CustomTkinter UI:
  1. "Live Monitor" tab with live camera feed, a canvas status LED, and manual debug triggers.
  2. "Inspection Gallery" tab which dynamically lists captured product runs by weld point so the operator can inspect and compare images.
- We added dynamic camera controls to open/close the connection and release /dev/video1 when closed.
- We refactored communication to use a double-queue system (ui_to_main_queue and main_to_ui_queue) for safety.
- We successfully pushed the code to the GitHub repository: https://github.com/markjosephdsgatdula-dotcom/Ras-PI-5-program.git

We are now ready to:
1. Capture training images at work today.
2. Develop a Python script (using MobileSAM / Segment Anything Model) to automatically generate the weld bead polygon boundaries (auto-labeling) so we don't have to trace them manually on Roboflow.

Please review the codebase, and let's start writing the auto-labeling script.
```
