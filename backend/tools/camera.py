# RANK: 2 - Setup OpenCV to read frames from the local webcam (cv2.VideoCapture).

import cv2
import threading
import time
import numpy as np

class LocalCameraStream:
    """
    A simple wrapper around OpenCV's VideoCapture to provide a continuous stream
    of frames from a local webcam. Runs the capture in a separate thread.
    """
    def __init__(self, device_id: int = 0, target_fps: int = 30):
        self.device_id = device_id
        self.target_fps = target_fps
        self.cap = None
        self.latest_frame = None
        self.is_running = False
        self.thread = None
        self.frame_count = 0

    def start(self):
        if self.is_running:
            return
            
        self.cap = cv2.VideoCapture(self.device_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera with device ID {self.device_id}")
            
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print(f"Started camera stream on device {self.device_id}")

    def _capture_loop(self):
        frame_time = 1.0 / self.target_fps
        
        while self.is_running:
            start_time = time.time()
            
            ret, frame = self.cap.read()
            if ret:
                # Store the most recent frame
                # cv2.read() returns BGR frames
                self.latest_frame = frame
                self.frame_count += 1
                
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)

    def get_latest_frame(self) -> np.ndarray | None:
        """Return the most recently captured frame."""
        if self.latest_frame is not None:
             # Return a copy to avoid threading race conditions on mutation
            return self.latest_frame.copy()
        return None

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        print("Camera stream stopped.")