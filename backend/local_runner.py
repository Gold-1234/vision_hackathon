import cv2
import time
import argparse
from processors import ObjectDetectionProcessor, FallDetectionProcessor
from processors.base import draw_bbox
from tools.camera import LocalCameraStream

def main(device_id: int):
    print("Initializing Vision System Local Runner...")
    
    # 1. Initialize the Processors
    # FPS doesn't strictly matter here since we are just pulling frames as fast as we process
    detector = ObjectDetectionProcessor(fps=30, confidence_threshold=0.5)
    fall_detector = FallDetectionProcessor(fps=30, confidence_threshold=0.5)
    
    # 2. Initialize Camera
    camera = LocalCameraStream(device_id=device_id, target_fps=30)
    camera.start()
    
    print("Waiting for camera to warm up...")
    time.sleep(2)
    
    print("Starting processing loop. Press 'q' to quit.")
    
    frame_count = 0
    try:
        while True:
            # Check for quit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            frame = camera.get_latest_frame()
            if frame is None:
                time.sleep(0.01)
                continue
                
            # Process the frame
            # The processor returns the annotated frame (boxes drawn)
            annotated_frame = detector.process_frame(frame_count, frame)
            
            # Fall detector expects the _detect synchronous method for now
            fall_detections = fall_detector._detect(frame_count, frame)
            fall_detector.latest_detections = fall_detections
            
            # Draw fall detections
            fall_detected = False
            for det in fall_detections:
                if det.get("is_falling", False):
                    fall_detected = True
                    annotated_frame = draw_bbox(annotated_frame, det.get("bbox", (0,0,0,0)), label="FALL DETECTED!", color=(0, 0, 255), thickness=3)

            fall_detector.fall_present = fall_detected
            frame_count += 1
            
            # Simulated event logging
            detections = getattr(detector, 'latest_detections', [])
            if len(detections) > 0 and frame_count % 30 == 0:
                print(f"Frame {frame_count} - Detected {len(detections)} objects. E.g. {detections[0]['label']}")
            if fall_detected and frame_count % 5 == 0:
                print(f"⚠️ Frame {frame_count} - FALL DETECTED!")
            
            # Display the result
            cv2.imshow('Vision Hackathon - Live Object & Fall Detection', annotated_frame)
            
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        print("Cleaning up...")
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Vision System Locally")
    parser.add_argument("--device", type=int, default=0, help="Camera device ID (default: 0)")
    args = parser.parse_args()
    main(args.device)
