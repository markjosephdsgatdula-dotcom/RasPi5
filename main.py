import queue
import time
import threading
import json
import os
from xmlrpc.server import SimpleXMLRPCServer
from src.trigger_handler import TriggerHandler
from src.camera_capture import CameraCapture
from src.ui_app import WeldMonitoringUI

# ─── GPIO Pin Configuration ───────────────────────────────────────────────────
TRIGGER_INPUT_PIN  = 17   # UR10e → Pi: "Capture now"
CONFIRM_OUTPUT_PIN = 27   # Pi → UR10e: "Image saved, you may move"
PRODUCT_DONE_PIN   = 22   # UR10e → Pi: "Product cycle complete"

# ─── Camera ───────────────────────────────────────────────────────────────────
CAMERA_INDEX       = 0    # Default camera index (/dev/video0). If incorrect, system will auto-scan.

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
session_lock = threading.Lock()


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

    ui_to_main_queue = queue.Queue()
    main_to_ui_queue = queue.Queue()

    camera = CameraCapture(camera_index=CAMERA_INDEX)
    if camera.is_open():
        if camera.camera_index != CAMERA_INDEX:
            main_to_ui_queue.put(('log', f"[SYSTEM] Configured camera index {CAMERA_INDEX} failed. Auto-detected and using index {camera.camera_index}."))
        else:
            main_to_ui_queue.put(('log', f"[SYSTEM] Camera opened at index {camera.camera_index}."))
    else:
        main_to_ui_queue.put(('log', f"[ERROR] Could not open camera at index {CAMERA_INDEX} or any fallback indices."))

    # 2. Check for an existing session to resume
    saved = load_state()
    if saved:
        main_to_ui_queue.put(('resume_hint', (saved["product_name"], saved["product_num"])))

    # ─── Callbacks (called from gpiozero background thread) ───────────────────

    def on_robot_trigger() -> bool:
        """Fires when UR10e sends capture signal on BCM 17 or via XML-RPC."""
        with session_lock:
            if not session["active"]:
                main_to_ui_queue.put(('log', "[WARNING] Trigger received but no session is active. Start a session first."))
                return False

            if not camera.is_open():
                main_to_ui_queue.put(('log', "[WARNING] Capture trigger received but camera is closed!"))
                return False

            weld_dir = os.path.join(
                BASE_SAVE_DIR,
                session["product_name"],
                f"weldpoint_{session['weld_index']:02d}"
            )

            main_to_ui_queue.put(('log', f"[TRIGGER] Capturing → {weld_dir}"))

            success, filepath, img = camera.capture_image(
                save_dir    = weld_dir,
                product_num = session["product_num"]
            )

            if success:
                main_to_ui_queue.put(('log', f"[SUCCESS] Saved: {os.path.basename(filepath)}"))
                main_to_ui_queue.put(('image', img))

                session["weld_index"] += 1
                save_state()
                main_to_ui_queue.put(('status', (session["product_name"],
                                           session["product_num"],
                                           session["weld_index"])))
                return True
            else:
                main_to_ui_queue.put(('log', "[ERROR] Capture failed."))
                return False

    def on_product_done():
        """Fires when UR10e sends product-done signal on BCM 22 or via XML-RPC."""
        with session_lock:
            if not session["active"]:
                return

            old_num = session["product_num"]
            session["product_num"]  += 1
            session["weld_index"]    = 1
            save_state()

        main_to_ui_queue.put(('log', f"[DONE] Product #{old_num:03d} complete → starting #{session['product_num']:03d}"))
        main_to_ui_queue.put(('status', (session["product_name"],
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
        main_to_ui_queue.put(('log', f"[INIT] GPIO ready — Capture=BCM{TRIGGER_INPUT_PIN}, "
                                     f"Confirm=BCM{CONFIRM_OUTPUT_PIN}, Done=BCM{PRODUCT_DONE_PIN}"))
    except Exception as e:
        main_to_ui_queue.put(('log', f"[WARNING] GPIO init failed (expected if not on Pi): {e}"))

    # 4. XML-RPC Server
    rpc_server = None
    class RobotXMLRPCInterface:
        def capture_weld(self) -> bool:
            main_to_ui_queue.put(('log', "[XML-RPC] Received capture_weld request"))
            return on_robot_trigger()

        def trigger_capture(self) -> bool:
            return self.capture_weld()

        def cycle_complete(self) -> bool:
            main_to_ui_queue.put(('log', "[XML-RPC] Received cycle_complete request"))
            on_product_done()
            return True

        def product_done(self) -> bool:
            return self.cycle_complete()

    try:
        rpc_server = SimpleXMLRPCServer(("0.0.0.0", 8000), logRequests=False, allow_none=True)
        rpc_server.register_instance(RobotXMLRPCInterface())

        rpc_thread = threading.Thread(target=rpc_server.serve_forever, daemon=True)
        rpc_thread.start()
        main_to_ui_queue.put(('log', "[INIT] XML-RPC server listening on port 8000"))
    except Exception as e:
        main_to_ui_queue.put(('log', f"[ERROR] Failed to start XML-RPC server: {e}"))

    # 5. Build UI
    app = WeldMonitoringUI(main_to_ui_queue, ui_to_main_queue)

    # 6. Live video feed thread
    is_running = True

    def live_feed():
        while is_running:
            if camera.is_open():
                ok, frame = camera.read_frame()
                if ok:
                    main_to_ui_queue.put(('image', frame))
            time.sleep(0.033)   # ~30 fps

    feed_thread = threading.Thread(target=live_feed, daemon=True)
    feed_thread.start()

    # 7. Queue handler for session_start and UI control events
    def session_monitor():
        """
        Dedicated thread that watches for messages on ui_to_main_queue
        and coordinates state updates.
        """
        nonlocal is_running
        while is_running:
            try:
                # Block for a short time to allow check of is_running flag
                item = ui_to_main_queue.get(timeout=0.2)
                msg_type, data = item

                if msg_type == 'session_start':
                    name = data

                    # If resuming, load previous counters for this product
                    saved_state = load_state()
                    if saved_state and saved_state.get("product_name") == name:
                        session["product_num"] = saved_state["product_num"]
                        session["weld_index"]  = saved_state["weld_index"]
                        main_to_ui_queue.put(('log', f"[RESUME] Resuming {name} at Product #{session['product_num']:03d}, Weld {session['weld_index']:02d}"))
                    else:
                        session["product_num"] = 1
                        session["weld_index"]  = 1

                    session["product_name"] = name
                    session["active"]       = True
                    save_state()

                    main_to_ui_queue.put(('show_monitor', None))
                    main_to_ui_queue.put(('log', f"[SESSION] Started: {name}"))
                    main_to_ui_queue.put(('status', (name, session["product_num"], session["weld_index"])))

                    # Send initial camera status to UI
                    cam_state = 'open' if camera.is_open() else 'closed'
                    main_to_ui_queue.put(('camera_status', cam_state))

                elif msg_type == 'camera_control':
                    action = data
                    if action == 'open':
                        success = camera.open_camera()
                        if success:
                            if camera.camera_index != CAMERA_INDEX:
                                msg = f"[SYSTEM] Camera index {CAMERA_INDEX} failed. Auto-detected and opened index {camera.camera_index}."
                            else:
                                msg = f"[SYSTEM] Camera connection opened (index {camera.camera_index})."
                            main_to_ui_queue.put(('log', msg))
                            main_to_ui_queue.put(('camera_status', 'open'))
                        else:
                            main_to_ui_queue.put(('log', f"[ERROR] Failed to open camera connection (tried index {CAMERA_INDEX} and fallbacks)."))
                            main_to_ui_queue.put(('camera_status', 'failed'))
                    elif action == 'close':
                        camera.close_camera()
                        main_to_ui_queue.put(('log', "[SYSTEM] Camera connection closed."))
                        main_to_ui_queue.put(('camera_status', 'closed'))

                elif msg_type == 'manual_trigger':
                    main_to_ui_queue.put(('log', "[USER] Manual trigger event simulated."))
                    on_robot_trigger()

                elif msg_type == 'manual_product_done':
                    main_to_ui_queue.put(('log', "[USER] Manual product cycle advance simulated."))
                    on_product_done()

            except queue.Empty:
                continue
            except Exception as e:
                try:
                    main_to_ui_queue.put(('log', f"[ERROR] monitor loop exception: {e}"))
                except Exception:
                    pass

    monitor_thread = threading.Thread(target=session_monitor, daemon=True)
    monitor_thread.start()

    # 8. Run UI main loop
    try:
        app.mainloop()
    finally:
        is_running = False
        if rpc_server:
            rpc_server.shutdown()
            rpc_server.server_close()
        feed_thread.join(timeout=1.0)
        camera.release()
        print("System shutdown cleanly.")


if __name__ == "__main__":
    main()
