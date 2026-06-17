import customtkinter as ctk
from PIL import Image
import cv2
import queue

# --- Appearance ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class WeldMonitoringUI(ctk.CTk):
    """
    Two-screen GUI:
      Screen 1 — Session Start: operator types product name and starts/resumes a session.
      Screen 2 — Live Monitor:  live camera feed, log panel, and status bar.
    """
    def __init__(self, msg_queue: queue.Queue):
        super().__init__()

        self.title("Robotic Weld Inspection Monitor")
        self.geometry("900x650")
        self.resizable(False, False)

        self.msg_queue       = msg_queue
        self.session_started = False

        # Build both screens; show start screen first
        self._build_start_screen()
        self._build_monitor_screen()
        self._show_start_screen()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(100, self._check_queue)

    # ─────────────────────────────── Screen 1: Session Start ────────────────────────────────

    def _build_start_screen(self):
        """Construct the session start frame (not shown yet)."""
        self.start_frame = ctk.CTkFrame(self)

        ctk.CTkLabel(self.start_frame, text="Weld Inspection System",
                     font=("Arial", 28, "bold")).pack(pady=(60, 4))
        ctk.CTkLabel(self.start_frame, text="Enter the product name to begin or resume a session.",
                     font=("Arial", 14), text_color="gray").pack(pady=(0, 40))

        ctk.CTkLabel(self.start_frame, text="Product Name:", font=("Arial", 16)).pack()
        self.product_name_entry = ctk.CTkEntry(self.start_frame, width=280, height=40,
                                               placeholder_text="e.g. SJKH-E3",
                                               font=("Arial", 15))
        self.product_name_entry.pack(pady=(8, 24))

        # Resume info label — populated from queue when state file exists
        self.resume_label = ctk.CTkLabel(self.start_frame, text="",
                                         font=("Arial", 13), text_color="#f0a500")
        self.resume_label.pack(pady=(0, 16))

        ctk.CTkButton(self.start_frame, text="Start Session", width=200, height=44,
                      font=("Arial", 15, "bold"),
                      command=self._on_start_session).pack(pady=(0, 20))

    def _show_start_screen(self):
        self.monitor_frame.place_forget()
        self.start_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _on_start_session(self):
        name = self.product_name_entry.get().strip()
        if not name:
            self.product_name_entry.configure(border_color="red")
            return
        self.product_name_entry.configure(border_color=("gray75", "gray30"))
        # Send session start event to main.py via queue
        self.msg_queue.put(('session_start', name))

    # ─────────────────────────────── Screen 2: Live Monitor ─────────────────────────────────

    def _build_monitor_screen(self):
        """Construct the live monitor frame (not shown yet)."""
        self.monitor_frame = ctk.CTkFrame(self)

        # Status bar at top
        status_bar = ctk.CTkFrame(self.monitor_frame, height=44, corner_radius=0)
        status_bar.pack(fill="x", padx=0, pady=(0, 0))

        self.lbl_product  = ctk.CTkLabel(status_bar, text="Product: —",
                                          font=("Consolas", 13, "bold"))
        self.lbl_product.pack(side="left", padx=20, pady=8)

        self.lbl_run      = ctk.CTkLabel(status_bar, text="Run: —",
                                          font=("Consolas", 13))
        self.lbl_run.pack(side="left", padx=20, pady=8)

        self.lbl_weld     = ctk.CTkLabel(status_bar, text="Weld Point: —",
                                          font=("Consolas", 13))
        self.lbl_weld.pack(side="left", padx=20, pady=8)

        # Camera feed
        self.image_label = ctk.CTkLabel(self.monitor_frame, text="Waiting for camera feed...",
                                         font=("Arial", 18))
        self.image_label.pack(fill="both", expand=True, padx=16, pady=(10, 4))

        # Log box
        self.log_textbox = ctk.CTkTextbox(self.monitor_frame, height=140,
                                           font=("Consolas", 13))
        self.log_textbox.pack(fill="x", padx=16, pady=(4, 16))

    def _show_monitor_screen(self):
        self.start_frame.place_forget()
        self.monitor_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.session_started = True

    # ─────────────────────────────── Public update methods ──────────────────────────────────

    def log_message(self, message: str):
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")

    def update_image(self, cv_image):
        try:
            pil = Image.fromarray(cv_image) if len(cv_image.shape) == 2 \
                  else Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(820, 430))
            self.image_label.configure(image=ctk_img, text="")
            self.image_label.image = ctk_img
        except Exception as e:
            self.log_message(f"[ERROR] Image display failed: {e}")

    def update_status(self, product_name: str, product_num: int, weld_index: int):
        self.lbl_product.configure(text=f"Product: {product_name}")
        self.lbl_run.configure(text=f"Run: #{product_num:03d}")
        self.lbl_weld.configure(text=f"Weld Point: {weld_index:02d}")

    def show_resume_hint(self, product_name: str, product_num: int):
        """Pre-fill start screen with existing session info."""
        self.product_name_entry.delete(0, "end")
        self.product_name_entry.insert(0, product_name)
        self.resume_label.configure(
            text=f"Resuming session — last saved at Product #{product_num:03d}")

    # ─────────────────────────────── Queue polling ───────────────────────────────────────────

    def _check_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()

                if msg_type == 'log':
                    self.log_message(data)
                elif msg_type == 'image':
                    self.update_image(data)
                elif msg_type == 'status':
                    # data = (product_name, product_num, weld_index)
                    self.update_status(*data)
                elif msg_type == 'show_monitor':
                    self._show_monitor_screen()
                elif msg_type == 'resume_hint':
                    # data = (product_name, product_num)
                    self.show_resume_hint(*data)

        except queue.Empty:
            pass
        finally:
            self.after(100, self._check_queue)

    def on_closing(self):
        self.destroy()
