import queue
import time
import threading
import json
import os
from src.trigger_handler import TriggerHandler
from src.camera_capture import CameraCapture
from src.ui_app import WeldMonitoringUI

# ─── GPIO Pin Configuration ───────────────────────────────────────────────────
TRIGGER_INPUT_PIN  = 17   # UR10e → Pi: "Capture now"
CONFIRM_OUTPUT_PIN = 27   # Pi → UR10e: "Image saved, you may move"
PRODUCT_DONE_PIN   = 22   # UR10e → Pi: "Product cycle complete"

# ─── Camera ───────────────────────────────────────────────────────────────────
CAMERA_INDEX       = 1    # /dev/video1 on this Pi (Microdia USB 2.0 Camera)

# ─── Data Storage ─────────────────────────────────────────────────────────────
BASE_SAVE_DIR      = "data/captured_images"
STATE_FILE         = "session_state.json"

# ─── Session State ────────────────────────────────────────────────────────────
# These are managed in the main thread via the event queue to avoid race conditions.
session = {
    "product_name": None,   # e.g. "SJKH-E3"
    "product_num":  1,      # increments on each product-done signal
    "weld_index":   1,      # increments on each capture, resets on product-done
    "active":       False,  # True after operator clicks "Start Session"
}


def save_state():
    """Persist session counters to disk so a reboot can resume mid-lot."""
    with open(STATE_FILE, "w") as f:
        json.dump({
            "product_name": session["product_name"],
            "product_num":  session["product_num"],
            "weld_index":   session["weld_index"],
        }, f, indent=2)


def load_state():
    """Return saved state dict if the file exists, else None."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def main():
    print("Starting Weld Inspection Monitor...")

    msg_queue = queue.Queue()

    # 1. Camera
    camera = CameraCapture(camera_index=CAMERA_INDEX)

    # 2. Check for an existing session to resume
    saved = load_state()
    if saved:
        msg_queue.put(('resume_hint', (saved["product_name"], saved["product_num"])))

    # ─── Callbacks (called from gpiozero background thread) ───────────────────

    def on_robot_trigger() -> bool:
        """Fires when UR10e sends capture signal on BCM 17."""
        if not session["active"]:
            msg_queue.put(('log', "[WARNING] Trigger received but no session is active. Start a session first."))
            return False

        weld_dir = os.path.join(
            BASE_SAVE_DIR,
            session["product_name"],
            f"weldpoint_{session['weld_index']:02d}"
        )

        msg_queue.put(('log', f"[TRIGGER] Capturing → {weld_dir}"))

        success, filepath, img = camera.capture_image(
            save_dir    = weld_dir,
            product_num = session["product_num"]
        )

        if success:
            msg_queue.put(('log', f"[SUCCESS] Saved: {os.path.basename(filepath)}"))
            msg_queue.put(('image', img))

            # Advance weld index and persist
            session["weld_index"] += 1
            save_state()
            msg_queue.put(('status', (session["product_name"],
                                       session["product_num"],
                                       session["weld_index"])))
            return True
        else:
            msg_queue.put(('log', "[ERROR] Capture failed."))
            return False

    def on_product_done():
        """Fires when UR10e sends product-done signal on BCM 22."""
        if not session["active"]:
            return

        old_num = session["product_num"]
        session["product_num"]  += 1
        session["weld_index"]    = 1
        save_state()

        msg_queue.put(('log', f"[DONE] Product #{old_num:03d} complete → starting #{session['product_num']:03d}"))
        msg_queue.put(('status', (session["product_name"],
                                   session["product_num"],
                                   session["weld_index"])))

    # 3. Hardware Trigger Handler
    try:
        handler = TriggerHandler(
            input_pin             = TRIGGER_INPUT_PIN,
            output_pin            = CONFIRM_OUTPUT_PIN,
            done_pin              = PRODUCT_DONE_PIN,
            capture_callback      = on_robot_trigger,
            product_done_callback = on_product_done,
        )
        msg_queue.put(('log', f"[INIT] GPIO ready — Capture=BCM{TRIGGER_INPUT_PIN}, "
                              f"Confirm=BCM{CONFIRM_OUTPUT_PIN}, Done=BCM{PRODUCT_DONE_PIN}"))
    except Exception as e:
        msg_queue.put(('log', f"[WARNING] GPIO init failed (expected if not on Pi): {e}"))

    # 4. Build UI
    app = WeldMonitoringUI(msg_queue)

    # 5. Live video feed thread
    is_running = True

    def live_feed():
        while is_running:
            ok, frame = camera.read_frame()
            if ok:
                msg_queue.put(('image', frame))
            time.sleep(0.033)   # ~30 fps

    feed_thread = threading.Thread(target=live_feed, daemon=True)
    feed_thread.start()

    # 6. Queue handler for session_start events (must patch session from main thread)
    #    We intercept 'session_start' messages before the UI sees them.
    original_get = msg_queue.get_nowait

    def _intercept_session_start():
        """Called by UI's check_queue → we hook session_start before UI side."""
        pass  # Actual interception done in a monitor thread below

    def session_monitor():
        """
        Dedicated thread that watches for 'session_start' messages and
        activates the session state.
        """
        while is_running:
            try:
                # Peek at queue without blocking
                item = msg_queue.get_nowait()
                msg_type, data = item

                if msg_type == 'session_start':
                    name = data

                    # If resuming, load previous counters for this product
                    saved_state = load_state()
                    if saved_state and saved_state.get("product_name") == name:
                        session["product_num"] = saved_state["product_num"]
                        session["weld_index"]  = saved_state["weld_index"]
                        msg_queue.put(('log', f"[RESUME] Resuming {name} at Product #{session['product_num']:03d}, Weld {session['weld_index']:02d}"))
                    else:
                        session["product_num"] = 1
                        session["weld_index"]  = 1

                    session["product_name"] = name
                    session["active"]       = True
                    save_state()

                    msg_queue.put(('show_monitor', None))
                    msg_queue.put(('log', f"[SESSION] Started: {name}"))
                    msg_queue.put(('status', (name, session["product_num"], session["weld_index"])))
                else:
                    # Put non-session items back
                    msg_queue.put((msg_type, data))

            except queue.Empty:
                time.sleep(0.05)

    monitor_thread = threading.Thread(target=session_monitor, daemon=True)
    monitor_thread.start()

    # 7. Run UI main loop
    try:
        app.mainloop()
    finally:
        is_running = False
        feed_thread.join(timeout=1.0)
        camera.release()
        print("System shutdown cleanly.")


if __name__ == "__main__":
    main()
