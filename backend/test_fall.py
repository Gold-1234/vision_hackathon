import cv2
import numpy as np
from processors.fall_detection import FallDetectionProcessor
import urllib.request
import os

def check_fall(image_path_or_url, is_url=False):
    processor = FallDetectionProcessor(fps=2.0)
    
    if is_url:
        print(f"Downloading {image_path_or_url}...")
        try:
            req = urllib.request.urlopen(image_path_or_url)
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
            frame = cv2.imdecode(arr, -1)
        except Exception as e:
            print(f"Failed to download image: {e}")
            return
    else:
        frame = cv2.imread(image_path_or_url)
        
    if frame is None:
        print("Could not load image.")
        return
        
    print("Running detection...")
    detections = processor._detect(0, frame)
    
    fall = False
    for det in detections:
        print(f"- Detected {det['label']} (conf: {det['confidence']:.2f})")
        if det.get("is_falling"):
            print("  --> FALL DETECTED! (ratio or keypoint triggered)")
            fall = True
            
    if not fall:
        print("  --> No fall detected.")

if __name__ == "__main__":
    print("Testing Fall Detection Model...")
    # URL of a person falling / lying down
    # Just a placeholder test image url:
    test_url = "https://raw.githubusercontent.com/ultralytics/yolov5/master/data/images/bus.jpg" 
    # Use bus.jpg (people standing) to verify no false positives
    check_fall(test_url, is_url=True)

