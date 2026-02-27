# RANK: 5 - Exports processor classes like ObjectDetectionProcessor for server.py.
# Processor imports — add each processor as it's implemented
from .object_detection import ObjectDetectionProcessor
from .toddler_processor import ToddlerProcessor
from .combined_video_publisher import CombinedVideoPublisher

try:
    from .fall_detection import FallDetectionProcessor
except ModuleNotFoundError:
    FallDetectionProcessor = None
# from .fall_detection import FallDetectionProcessor
# from .face_recognition import FaceRecognitionProcessor
# from .toddler_detection import ToddlerDetectionProcessor
# from .image_summary import ImageSummaryProcessor
# from .edge_proximity import EdgeProximityProcessor
# from .danger_zone import DangerZoneProcessor
# from .danger_proximity import DangerProximityProcessor
# from .cry_detection import CryDetectionProcessor
