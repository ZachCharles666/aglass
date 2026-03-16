# Inference module - YOLO edge inference
from .models import Detection, DetectionResult
from .runner import InferenceRunner, get_inference_runner, set_inference_runner
