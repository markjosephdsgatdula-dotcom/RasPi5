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

        # Force CAP_V4L2 backend — avoids Pi 5 GStreamer pipeline failures on USB cams
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)

        if not self.cap.isOpened():
            print(f"Warning: Failed to open camera at index {self.camera_index}")

    def read_frame(self):
        """
        Grab a single frame for live preview (not saved to disk).

        Returns:
            Tuple: (success (bool), gray_frame (ndarray or None))
        """
        if not self.cap.isOpened():
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
        if not self.cap.isOpened():
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
        if self.cap.isOpened():
            self.cap.release()
