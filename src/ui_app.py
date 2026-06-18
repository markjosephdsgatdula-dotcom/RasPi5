import customtkinter as ctk
from PIL import Image
import cv2
import queue
import os

# --- Appearance ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class WeldMonitoringUI(ctk.CTk):
    """
    Two-screen GUI:
      Screen 1 — Session Start: operator types product name and starts/resumes a session.
      Screen 2 — Main Dashboard: Tabview with Live Monitor and Inspection Gallery.
    """
    def __init__(self, main_queue: queue.Queue, ui_queue: queue.Queue):
        super().__init__()

        self.title("Robotic Weld Inspection Monitor")
        self.geometry("900x650")
        self.resizable(False, False)

        self.main_queue = main_queue  # queue for incoming messages (Main -> UI)
        self.ui_queue   = ui_queue    # queue for outgoing messages (UI -> Main)
        self.session_started = False

        # Gallery state variables
        self.gallery_images = []
        self.current_gallery_index = -1
        self.gallery_buttons = []

        # Create base directory if missing
        os.makedirs("data/captured_images", exist_ok=True)

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
        # Send session start event to main.py
        self.ui_queue.put(('session_start', name))

    # ─────────────────────────────── Screen 2: Dashboard ────────────────────────────────────

    def _build_monitor_screen(self):
        """Construct the main tabbed dashboard monitor frame."""
        self.monitor_frame = ctk.CTkFrame(self)

        # Tabview layout
        self.tabview = ctk.CTkTabview(self.monitor_frame, command=self._on_tab_changed)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_monitor = self.tabview.add("Live Monitor")
        self.tab_gallery = self.tabview.add("Inspection Gallery")

        self._build_live_monitor_tab()
        self._build_inspection_gallery_tab()

    def _show_monitor_screen(self):
        self.start_frame.place_forget()
        self.monitor_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.session_started = True
        self.tabview.set("Live Monitor")

    # ─────────────────────────────── Live Monitor Tab ───────────────────────────────────────

    def _build_live_monitor_tab(self):
        """Construct elements inside the Live Monitor tab."""
        # 1. Status Bar
        status_bar = ctk.CTkFrame(self.tab_monitor, height=40, corner_radius=6)
        status_bar.pack(fill="x", padx=4, pady=(0, 8))

        self.lbl_product  = ctk.CTkLabel(status_bar, text="Product: —",
                                          font=("Consolas", 13, "bold"))
        self.lbl_product.pack(side="left", padx=16, pady=8)

        self.lbl_run      = ctk.CTkLabel(status_bar, text="Run: —",
                                          font=("Consolas", 13))
        self.lbl_run.pack(side="left", padx=16, pady=8)

        self.lbl_weld     = ctk.CTkLabel(status_bar, text="Weld Point: —",
                                          font=("Consolas", 13))
        self.lbl_weld.pack(side="left", padx=16, pady=8)

        # 2. Main horizontal split
        left_panel = ctk.CTkFrame(self.tab_monitor, fg_color="transparent")
        left_panel.pack(side="left", fill="both", expand=True, padx=(4, 8))

        right_panel = ctk.CTkFrame(self.tab_monitor, width=210)
        right_panel.pack(side="right", fill="y", padx=4)
        right_panel.pack_propagate(False)

        # 3. Left Panel Content (Live Camera Label + Console Logs)
        self.image_label = ctk.CTkLabel(left_panel, text="Camera Offline",
                                         font=("Arial", 16), fg_color="#181818", corner_radius=8)
        self.image_label.pack(fill="both", expand=True, pady=(0, 8))

        self.log_textbox = ctk.CTkTextbox(left_panel, height=130, font=("Consolas", 12))
        self.log_textbox.pack(fill="x")

        # 4. Right Panel Content (Camera controls & simulation)
        ctk.CTkLabel(right_panel, text="CAMERA INTERFACE", font=("Arial", 12, "bold"), text_color="gray").pack(pady=(16, 8))
        
        # Camera Connection status LED indicator
        status_led_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        status_led_frame.pack(pady=4)

        self.cam_canvas = ctk.CTkCanvas(status_led_frame, width=14, height=14, bg="#2b2b2b", highlightthickness=0)
        self.cam_canvas.pack(side="left", padx=(0, 8))
        self.cam_led = self.cam_canvas.create_oval(2, 2, 12, 12, fill="red")

        self.cam_status_text = ctk.CTkLabel(status_led_frame, text="Camera: Closed", font=("Arial", 13))
        self.cam_status_text.pack(side="left")

        # Connection Buttons
        self.btn_open_cam = ctk.CTkButton(right_panel, text="Open Camera", height=32,
                                          fg_color=("#10b981", "#059669"), hover_color=("#059669", "#047857"),
                                          command=self._on_open_camera)
        self.btn_open_cam.pack(fill="x", padx=16, pady=(12, 8))

        self.btn_close_cam = ctk.CTkButton(right_panel, text="Close Camera", height=32,
                                           fg_color=("#ef4444", "#dc2626"), hover_color=("#dc2626", "#b91c1c"),
                                           command=self._on_close_camera)
        self.btn_close_cam.pack(fill="x", padx=16, pady=4)

        # Separator line
        sep = ctk.CTkFrame(right_panel, height=2, fg_color=("gray75", "gray30"))
        sep.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(right_panel, text="SIMULATION & OVERRIDE", font=("Arial", 12, "bold"), text_color="gray").pack(pady=(0, 8))

        self.btn_manual_trigger = ctk.CTkButton(right_panel, text="Manual Capture", height=32,
                                                fg_color=("#3b82f6", "#2563eb"), hover_color=("#2563eb", "#1d4ed8"),
                                                command=self._on_manual_trigger)
        self.btn_manual_trigger.pack(fill="x", padx=16, pady=6)

        self.btn_next_product = ctk.CTkButton(right_panel, text="Next Product Run", height=32,
                                              fg_color=("#8b5cf6", "#7c3aed"), hover_color=("#7c3aed", "#6d28d9"),
                                              command=self._on_manual_product_done)
        self.btn_next_product.pack(fill="x", padx=16, pady=6)

    # ─────────────────────────────── Inspection Gallery Tab ──────────────────────────────────

    def _build_inspection_gallery_tab(self):
        """Construct elements inside the Inspection Gallery tab."""
        # Left sidebar panel for lot and point browsing
        self.gallery_sidebar = ctk.CTkFrame(self.tab_gallery, width=240)
        self.gallery_sidebar.pack(side="left", fill="y", padx=4, pady=4)
        self.gallery_sidebar.pack_propagate(False)

        # Right main preview panel
        self.gallery_main = ctk.CTkFrame(self.tab_gallery, fg_color="transparent")
        self.gallery_main.pack(side="right", fill="both", expand=True, padx=(8, 4), pady=4)

        # Sidebar dropdowns & selections
        ctk.CTkLabel(self.gallery_sidebar, text="INSPECTION BROWSER", font=("Arial", 13, "bold"), text_color="gray").pack(pady=(12, 12))

        # 1. Product Selection
        ctk.CTkLabel(self.gallery_sidebar, text="Product Lot:", font=("Arial", 12)).pack(anchor="w", padx=16, pady=(4, 2))
        self.gallery_product_combo = ctk.CTkComboBox(self.gallery_sidebar, width=200, command=self._on_product_selected)
        self.gallery_product_combo.pack(padx=16, pady=(0, 10))

        # 2. Weld Point Selection
        ctk.CTkLabel(self.gallery_sidebar, text="Weld Point:", font=("Arial", 12)).pack(anchor="w", padx=16, pady=(4, 2))
        self.gallery_weld_combo = ctk.CTkComboBox(self.gallery_sidebar, width=200, command=self._on_weld_point_selected)
        self.gallery_weld_combo.pack(padx=16, pady=(0, 14))

        # 3. Refresh Action
        self.gallery_refresh_btn = ctk.CTkButton(self.gallery_sidebar, text="Refresh Folders", height=28,
                                                 fg_color="gray30", hover_color="gray40",
                                                 command=self._refresh_gallery_products)
        self.gallery_refresh_btn.pack(fill="x", padx=16, pady=(0, 10))

        # 4. Scrollable List of Runs
        self.gallery_list_frame = ctk.CTkScrollableFrame(self.gallery_sidebar, label_text="Captured Runs")
        self.gallery_list_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # Right side Details Panel (Metadata display at top)
        self.gallery_meta_frame = ctk.CTkFrame(self.gallery_main, height=35, corner_radius=6)
        self.gallery_meta_frame.pack(fill="x", pady=(0, 8))
        self.gallery_meta_frame.pack_propagate(False)

        self.gallery_meta_lbl = ctk.CTkLabel(self.gallery_meta_frame, text="Select a weld run to inspect",
                                              font=("Consolas", 12, "bold"))
        self.gallery_meta_lbl.pack(fill="both", padx=12, pady=6)

        # Right side central image view
        self.gallery_image_label = ctk.CTkLabel(self.gallery_main, text="No Image Loaded",
                                                 font=("Arial", 16), fg_color="#181818", corner_radius=8)
        self.gallery_image_label.pack(fill="both", expand=True, pady=(0, 8))

        # Bottom navigation controls
        nav_frame = ctk.CTkFrame(self.gallery_main, height=44, corner_radius=6)
        nav_frame.pack(fill="x")

        self.gallery_prev_btn = ctk.CTkButton(nav_frame, text="◀ Previous Run", width=120, height=32,
                                              command=self._on_prev_gallery_image)
        self.gallery_prev_btn.pack(side="left", padx=16, pady=6)

        self.gallery_counter_lbl = ctk.CTkLabel(nav_frame, text="—", font=("Arial", 13, "bold"))
        self.gallery_counter_lbl.pack(side="left", fill="both", expand=True)

        self.gallery_next_btn = ctk.CTkButton(nav_frame, text="Next Run ▶", width=120, height=32,
                                              command=self._on_next_gallery_image)
        self.gallery_next_btn.pack(side="right", padx=16, pady=6)

    # ─────────────────────────────── UI Callbacks & Event Queues ──────────────────────────────

    def _on_open_camera(self):
        self.ui_queue.put(('camera_control', 'open'))

    def _on_close_camera(self):
        self.ui_queue.put(('camera_control', 'close'))

    def _on_manual_trigger(self):
        self.ui_queue.put(('manual_trigger', None))

    def _on_manual_product_done(self):
        self.ui_queue.put(('manual_product_done', None))

    def _on_tab_changed(self):
        """Automatically refresh folder lists when changing to the gallery view."""
        if self.tabview.get() == "Inspection Gallery":
            self._refresh_gallery_products()

    # ─────────────────────────────── Gallery File Scanning ───────────────────────────────────

    def _refresh_gallery_products(self):
        """Scans directories under data/captured_images to populate combo values."""
        base_dir = "data/captured_images"
        products = []
        if os.path.exists(base_dir):
            products = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        products.sort()

        if products:
            self.gallery_product_combo.configure(values=products)
            # Default to the current active product if available, else first in list
            current_active = self.lbl_product.cget("text").replace("Product: ", "").strip()
            if current_active in products:
                self.gallery_product_combo.set(current_active)
                self._on_product_selected(current_active)
            else:
                self.gallery_product_combo.set(products[0])
                self._on_product_selected(products[0])
        else:
            self.gallery_product_combo.configure(values=["No products found"])
            self.gallery_product_combo.set("No products found")
            self.gallery_weld_combo.configure(values=["—"])
            self.gallery_weld_combo.set("—")
            self._clear_gallery_list()
            self.gallery_image_label.configure(image=None, text="No captured images to display.")

    def _on_product_selected(self, product):
        """Fires when product lot is changed; scans and populates weld points."""
        if product == "No products found":
            return
        base_dir = os.path.join("data/captured_images", product)
        weld_points = []
        if os.path.exists(base_dir):
            weld_points = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.startswith("weldpoint_")]
        weld_points.sort()

        if weld_points:
            self.gallery_weld_combo.configure(values=weld_points)
            self.gallery_weld_combo.set(weld_points[0])
            self._on_weld_point_selected(weld_points[0])
        else:
            self.gallery_weld_combo.configure(values=["No weldpoints found"])
            self.gallery_weld_combo.set("No weldpoints found")
            self._clear_gallery_list()
            self.gallery_image_label.configure(image=None, text="No captured images in this product.")

    def _on_weld_point_selected(self, weld_point):
        """Fires when weld point directory is changed; scans and populates files."""
        product = self.gallery_product_combo.get()
        if weld_point == "No weldpoints found" or product == "No products found":
            return
        base_dir = os.path.join("data/captured_images", product, weld_point)
        images = []
        if os.path.exists(base_dir):
            images = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.lower().endswith(".jpg")]
        images.sort()  # Naming convention makes alphabetical sort chronological

        self._clear_gallery_list()
        self.gallery_images = images
        self.current_gallery_index = -1

        if images:
            for idx, filepath in enumerate(images):
                filename = os.path.basename(filepath)
                parts = filename.replace(".jpg", "").split("_")
                if len(parts) >= 4:
                    time_str = f"{parts[3][:2]}:{parts[3][2:4]}:{parts[3][4:6]}"
                    run_str = f"Run #{parts[1]} ({time_str})"
                else:
                    run_str = filename

                btn = ctk.CTkButton(self.gallery_list_frame, text=run_str, anchor="w",
                                     fg_color="transparent", hover_color=("gray75", "gray30"),
                                     text_color=("black", "white"),
                                     command=lambda path=filepath, i=idx: self._select_gallery_image(path, i))
                btn.pack(fill="x", padx=4, pady=2)
                self.gallery_buttons.append(btn)

            # Pre-select first image
            self._select_gallery_image(images[0], 0)
        else:
            self.gallery_image_label.configure(image=None, text="No images found for this weldpoint.")
            self.gallery_meta_lbl.configure(text="No Image Loaded")
            self.gallery_counter_lbl.configure(text="—")

    def _clear_gallery_list(self):
        """Empties the scrollable list of buttons."""
        for w in self.gallery_list_frame.winfo_children():
            w.destroy()
        self.gallery_buttons = []
        self.gallery_images = []
        self.current_gallery_index = -1

    def _select_gallery_image(self, filepath, index):
        """Sets active list item highlighting and loads the image."""
        self.current_gallery_index = index
        for i, btn in enumerate(self.gallery_buttons):
            if i == index:
                btn.configure(fg_color=("#3a7ebf", "#1f538d"), text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("black", "white"))
        self._display_gallery_image(filepath)

    def _display_gallery_image(self, filepath):
        """Reads image from disk and displays in details viewer."""
        try:
            cv_img = cv2.imread(filepath)
            if cv_img is None:
                raise Exception("Failed to decode image file.")

            pil = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(580, 360))
            self.gallery_image_label.configure(image=ctk_img, text="")
            self.gallery_image_label.image = ctk_img

            # Display meta details
            filename = os.path.basename(filepath)
            parts = filename.replace(".jpg", "").split("_")
            if len(parts) >= 4:
                run_num = parts[1]
                date_str = f"{parts[2][:4]}-{parts[2][4:6]}-{parts[2][6:]}"
                time_str = f"{parts[3][:2]}:{parts[3][2:4]}:{parts[3][4:6]}"
                meta_text = f"Product: {self.gallery_product_combo.get()}  |  Weld: {self.gallery_weld_combo.get()}  |  Run: #{run_num}  |  Captured: {date_str} {time_str}"
            else:
                meta_text = filename

            self.gallery_meta_lbl.configure(text=meta_text)
            total = len(self.gallery_images)
            self.gallery_counter_lbl.configure(text=f"Run {self.current_gallery_index + 1} of {total}")
        except Exception as e:
            self.gallery_image_label.configure(image=None, text=f"[ERROR] Failed to load image:\n{e}")
            self.gallery_meta_lbl.configure(text="Error Loading Image")
            self.gallery_counter_lbl.configure(text="—")

    def _on_prev_gallery_image(self):
        if not self.gallery_images or self.current_gallery_index <= 0:
            return
        new_idx = self.current_gallery_index - 1
        self._select_gallery_image(self.gallery_images[new_idx], new_idx)

    def _on_next_gallery_image(self):
        if not self.gallery_images or self.current_gallery_index >= len(self.gallery_images) - 1:
            return
        new_idx = self.current_gallery_index + 1
        self._select_gallery_image(self.gallery_images[new_idx], new_idx)

    # ─────────────────────────────── Status update methods ──────────────────────────────────

    def log_message(self, message: str):
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")

    def update_image(self, cv_image):
        """Update live camera label with new video frame."""
        try:
            pil = Image.fromarray(cv_image) if len(cv_image.shape) == 2 \
                  else Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
            # Height 360, width 640 to fit comfortably in Live Monitor
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(640, 360))
            self.image_label.configure(image=ctk_img, text="")
            self.image_label.image = ctk_img
        except Exception as e:
            self.log_message(f"[ERROR] Live frame update failed: {e}")

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

    def update_camera_status(self, status: str):
        """Update camera indicator LED and placeholder labels based on backend states."""
        if status == 'open':
            self.cam_canvas.itemconfig(self.cam_led, fill="#2ecc71")
            self.cam_status_text.configure(text="Camera: Connected", text_color="#2ecc71")
        elif status == 'closed':
            self.cam_canvas.itemconfig(self.cam_led, fill="#e74c3c")
            self.cam_status_text.configure(text="Camera: Disconnected", text_color="#e74c3c")
            self._show_camera_offline(failed=False)
        elif status == 'failed':
            self.cam_canvas.itemconfig(self.cam_led, fill="#e74c3c")
            self.cam_status_text.configure(text="Camera: Error", text_color="#e74c3c")
            self._show_camera_offline(failed=True)

    def _show_camera_offline(self, failed=False):
        msg = "CAMERA OFFLINE\n(Click 'Open Camera' to connect)"
        if failed:
            msg = "CAMERA CONNECTION FAILED\n(Check USB / dev index configuration)"
        self.image_label.configure(image=None, text=msg, text_color="red" if failed else "gray")
        self.image_label.image = None

    # ─────────────────────────────── Queue polling ───────────────────────────────────────────

    def _check_queue(self):
        """Poll the incoming main_queue for coordinate messages."""
        try:
            while True:
                msg_type, data = self.main_queue.get_nowait()

                if msg_type == 'log':
                    self.log_message(data)
                elif msg_type == 'image':
                    self.update_image(data)
                elif msg_type == 'status':
                    self.update_status(*data)
                elif msg_type == 'show_monitor':
                    self._show_monitor_screen()
                elif msg_type == 'resume_hint':
                    self.show_hint = True
                    self.show_resume_hint(*data)
                elif msg_type == 'camera_status':
                    self.update_camera_status(data)

        except queue.Empty:
            pass
        finally:
            self.after(100, self._check_queue)

    def on_closing(self):
        self.destroy()
