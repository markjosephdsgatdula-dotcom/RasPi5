import cv2
import os
from datetime import datetime

class CameraCapture:
    """
    Handles camera connection, live preview frames, and triggered image saves.
    Images are saved to a dynamically provided directory on each capture call.
    """
    def __init__(self, camera_index: int = 1):
        """
        Args:
            camera_index (int): V4L2 video device index (1 on this Pi).
        """
        self.camera_index = camera_index
        self.cap = None
        self.open_camera()

    def open_camera(self) -> bool:
        """Open or re-open the camera device if closed."""
        import sys
        if self.is_open():
            return True

        # Determine if we should try V4L2 backend (Linux/Pi specific)
        use_v4l2 = sys.platform.startswith('linux')

        # 1. Try preferred index with CAP_V4L2 backend if on Linux
        if use_v4l2:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            if self.is_open():
                # Verify we can read a frame (metadata channels might open but fail reading)
                ret, _ = self.cap.read()
                if ret:
                    return True
            self.close_camera()

        # 2. Try preferred index with default backend (CAP_ANY)
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_ANY)
        if self.is_open():
            ret, _ = self.cap.read()
            if ret:
                return True
        self.close_camera()

        # 3. Fallback Scan: Try to find any working camera index (0 to 7)
        print(f"[CAMERA] Failed to open camera at index {self.camera_index}. Scanning fallback indices...")
        for idx in range(8):
            if idx == self.camera_index:
                continue

            # Try with V4L2 first if on Linux
            if use_v4l2:
                self.cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                if self.is_open():
                    ret, _ = self.cap.read()
                    if ret:
                        self.camera_index = idx
                        print(f"[CAMERA] Successfully fell back to index {idx} (V4L2)")
                        return True
                self.close_camera()

            # Try with default backend
            self.cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
            if self.is_open():
                ret, _ = self.cap.read()
                if ret:
                    self.camera_index = idx
                    print(f"[CAMERA] Successfully fell back to index {idx} (CAP_ANY)")
                    return True
            self.close_camera()

        return False

    def close_camera(self):
        """Release the camera resource."""
        if self.cap is not None:
            if self.cap.isOpened():
                self.cap.release()
            self.cap = None

    def is_open(self) -> bool:
        """Check if camera device is initialized and open."""
        return self.cap is not None and self.cap.isOpened()

    def read_frame(self):
        """
        Grab a single frame for live preview (not saved to disk).

        Returns:
            Tuple: (success (bool), gray_frame (ndarray or None))
        """
        if not self.is_open():
            return False, None

        ret, frame = self.cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            # Flip vertically only (0) to correct upside-down camera mount
            return True, cv2.flip(gray, 0)

        return False, None

    def capture_image(self, save_dir: str, product_num: int):
        """
        Capture and save a triggered weld inspection image.

        Naming convention: product_{num:03d}_{YYYYMMDD}_{HHMMSS}.jpg

        Args:
            save_dir (str):    Full path to the target weld-point folder.
            product_num (int): Current product run number (for filename).

        Returns:
            Tuple: (success (bool), filepath (str or None), gray_frame (ndarray or None))
        """
        if not self.is_open():
            return False, None, None

        ret, frame = self.cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            gray = cv2.flip(gray, 0)   # apply same orientation correction

            # Named by product number + timestamp for easy chronological sorting
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename  = f"product_{product_num:03d}_{timestamp}.jpg"

            os.makedirs(save_dir, exist_ok=True)   # create folder on the fly if needed
            filepath = os.path.join(save_dir, filename)
            cv2.imwrite(filepath, gray)

            return True, filepath, gray

        return False, None, None

    def release(self):
        """Release the camera resource."""
        self.close_camera()
