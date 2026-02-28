import numpy as np
from processors.fall_detection import FallDetectionProcessor

def test():
    print("Testing FallDetectionProcessor Init...")
    processor = FallDetectionProcessor(fps=2.0)
    
    print("Testing processing on random frame...")
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # We call _detect directly to test the synchronous logic
    detections = processor._detect(0, frame)
    print("Detections on random noise:", detections)
    print("Test passed.")

if __name__ == "__main__":
    test()
