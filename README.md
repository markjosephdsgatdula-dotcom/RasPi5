# Robotic Weld Inspection System

This project is Phase 1 of a machine vision system designed for a Raspberry Pi 5 with a UR10e Robot arm.

## Hardware Stack
*   **Host:** Raspberry Pi 5
*   **AI Accelerator:** Raspberry Pi AI Hat+ (Hailo-8L) - *Planned for Phase 2*
*   **Robot:** UR10e (PolyScope 5.13)
*   **Camera:** Monochrome USB / Ribbon Camera

## Phase 1 Capabilities
The current software provides:
1.  **GPIO Hardware Triggering**: Listens for a High signal from the UR10e to capture an image natively, responding with a 100ms acknowledge pulse.
2.  **Camera Capture**: Uses OpenCV to capture monochrome image frames instantly upon hardware trigger.
3.  **Data Logging**: Extensively named logs organized by timestamp (`YYYYMMDD_HHMMSS_micros.jpg`) and sorted locally to `data/captured_images/` for prospective model training.
4.  **Monitoring App**: A lightweight, thread-safe CustomTkinter Dashboard rendering the live system log and evaluating the most recently captured frames dynamically.

## Directory Structure
```
weld_inspection_system/
├── requirements.txt
├── README.md
├── main.py
├── src/
│   ├── trigger_handler.py     # Wraps `gpiozero` to bind hardware interrupts
│   ├── camera_capture.py      # Automates OpenCV framing and file logging
│   └── ui_app.py              # A CustomTkinter queue-polling dashboard GUI
└── data/
    └── captured_images/       # Generated automatically on capture
```

## Setup Instructions

**1. Create Virtual Environment (Optional but recommended)**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**2. Install Core Dependencies**
On the Raspberry Pi 5, the most optimal way to install packages for hardware control is using `apt` rather than Python's `pip`, but you can rely on the provided requirements file:
```bash
# Recommended hardware commands
sudo apt update
sudo apt install python3-opencv python3-gpiozero

# UI Setup
pip install -r requirements.txt
```

**3. Execution**
To boot the monitoring terminal and authorize the hardware listener (Note: Triggering GPIO inputs requires root or video/dialout group access depending on Pi config):
```bash
python main.py
```

## Phase 2 Architecture Prelude (Future)
The project structure encapsulates capture/trigger methodologies cleanly to prepare for **AI Inference**. The captured frames in Phase 1 will be leveraged as a dataset. Once the PyTorch model/Hailo model is parsed, `main.py` can bridge the `image_array` to the inference engine to classify the weld categorically (Good, Misaligned, Defect) directly before saving it or returning a definitive signal to the UR10e arm.
