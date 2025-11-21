"""
Detection Engine
YOLOv8-based person detection with GPU acceleration support.
"""

import cv2
import torch
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import time

from ultralytics import YOLO
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Detection:
    """Represents a single person detection."""
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    class_id: int
    class_name: str
    frame_id: int = 0
    timestamp: float = 0.0


class DetectionEngine:
    """
    YOLOv8-based detection engine for person detection.

    Features:
    - GPU acceleration (CUDA, MPS, CPU fallback)
    - Configurable confidence and IOU thresholds
    - Class filtering (person-only detection)
    - Batch processing support
    - Performance monitoring
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize detection engine.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        detection_config = self.config.get('detection', {})

        # Model settings
        self.model_name = detection_config.get('model', 'yolov8n.pt')
        self.confidence_threshold = detection_config.get('confidence_threshold', 0.5)
        self.iou_threshold = detection_config.get('iou_threshold', 0.45)
        self.device = detection_config.get('device', 'cuda')
        self.half_precision = detection_config.get('half_precision', False)
        self.target_classes = detection_config.get('target_classes', [0])  # 0 = person

        # Model
        self.model: Optional[YOLO] = None
        self.is_initialized = False

        # Statistics
        self.total_detections = 0
        self.total_inference_time = 0.0
        self.frame_count = 0

        logger.info("Detection Engine initialized")

    def initialize(self) -> bool:
        """
        Initialize YOLO model and prepare for inference.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Determine device
            device = self._get_device()
            logger.info(f"Using device: {device}")

            # Load model
            model_path = self._get_model_path()
            logger.info(f"Loading YOLO model: {model_path}")

            self.model = YOLO(model_path)

            # Set device
            self.model.to(device)

            # Enable half precision if requested and supported
            if self.half_precision and device in ['cuda', 'mps']:
                logger.info("Enabling half-precision (FP16) inference")

            self.is_initialized = True
            logger.info("Detection engine initialized successfully")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize detection engine: {e}")
            return False

    def _get_device(self) -> str:
        """
        Determine the best available device.

        Returns:
            Device string ('cuda', 'mps', or 'cpu')
        """
        requested_device = self.device.lower()

        if requested_device == 'cuda' and torch.cuda.is_available():
            return 'cuda'
        elif requested_device == 'mps' and torch.backends.mps.is_available():
            return 'mps'
        else:
            if requested_device != 'cpu':
                logger.warning(f"Requested device '{requested_device}' not available, using CPU")
            return 'cpu'

    def _get_model_path(self) -> str:
        """
        Get full path to model file.

        Returns:
            Path to model file
        """
        # Check if model is in models directory
        project_root = Path(__file__).parent.parent.parent
        model_dir = project_root / "app" / "models"
        model_path = model_dir / self.model_name

        if model_path.exists():
            return str(model_path)

        # If not found, ultralytics will download it automatically
        logger.info(f"Model not found locally, will download: {self.model_name}")
        return self.model_name

    def detect(
        self,
        frame: np.ndarray,
        confidence_threshold: Optional[float] = None,
        return_raw: bool = False
    ) -> List[Detection]:
        """
        Detect persons in a frame.

        Args:
            frame: Input frame (BGR format)
            confidence_threshold: Override default confidence threshold
            return_raw: Return raw YOLO results instead of Detection objects

        Returns:
            List of Detection objects
        """
        if not self.is_initialized:
            logger.error("Detection engine not initialized")
            return []

        try:
            start_time = time.time()

            # Run inference
            results = self.model(
                frame,
                conf=confidence_threshold or self.confidence_threshold,
                iou=self.iou_threshold,
                classes=self.target_classes,
                verbose=False,
                half=self.half_precision
            )

            inference_time = time.time() - start_time

            # Update statistics
            self.frame_count += 1
            self.total_inference_time += inference_time

            if return_raw:
                return results

            # Parse results
            detections = []
            for result in results:
                boxes = result.boxes
                for i in range(len(boxes)):
                    # Get box coordinates (xyxy format)
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = map(int, xyxy)

                    # Convert to xywh format
                    x, y, w, h = x1, y1, x2 - x1, y2 - y1

                    # Get confidence and class
                    confidence = float(boxes.conf[i])
                    class_id = int(boxes.cls[i])

                    # Get class name
                    class_name = self.model.names[class_id]

                    detection = Detection(
                        bbox=(x, y, w, h),
                        confidence=confidence,
                        class_id=class_id,
                        class_name=class_name,
                        frame_id=self.frame_count,
                        timestamp=time.time()
                    )

                    detections.append(detection)

            self.total_detections += len(detections)

            return detections

        except Exception as e:
            logger.error(f"Error during detection: {e}")
            return []

    def detect_batch(
        self,
        frames: List[np.ndarray],
        confidence_threshold: Optional[float] = None
    ) -> List[List[Detection]]:
        """
        Detect persons in multiple frames (batch processing).

        Args:
            frames: List of input frames
            confidence_threshold: Override default confidence threshold

        Returns:
            List of detection lists (one per frame)
        """
        if not self.is_initialized:
            logger.error("Detection engine not initialized")
            return [[] for _ in frames]

        try:
            start_time = time.time()

            # Run batch inference
            results = self.model(
                frames,
                conf=confidence_threshold or self.confidence_threshold,
                iou=self.iou_threshold,
                classes=self.target_classes,
                verbose=False,
                half=self.half_precision
            )

            inference_time = time.time() - start_time

            # Update statistics
            self.frame_count += len(frames)
            self.total_inference_time += inference_time

            # Parse results for each frame
            all_detections = []
            for frame_idx, result in enumerate(results):
                detections = []
                boxes = result.boxes

                for i in range(len(boxes)):
                    # Get box coordinates
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = map(int, xyxy)
                    x, y, w, h = x1, y1, x2 - x1, y2 - y1

                    # Get confidence and class
                    confidence = float(boxes.conf[i])
                    class_id = int(boxes.cls[i])
                    class_name = self.model.names[class_id]

                    detection = Detection(
                        bbox=(x, y, w, h),
                        confidence=confidence,
                        class_id=class_id,
                        class_name=class_name,
                        frame_id=self.frame_count - len(frames) + frame_idx,
                        timestamp=time.time()
                    )

                    detections.append(detection)

                all_detections.append(detections)
                self.total_detections += len(detections)

            return all_detections

        except Exception as e:
            logger.error(f"Error during batch detection: {e}")
            return [[] for _ in frames]

    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Detection],
        show_confidence: bool = True,
        show_class: bool = True,
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw detection bounding boxes on frame.

        Args:
            frame: Input frame
            detections: List of detections to draw
            show_confidence: Show confidence score
            show_class: Show class name
            color: Box color (BGR)
            thickness: Box line thickness

        Returns:
            Frame with drawn detections
        """
        output_frame = frame.copy()

        for detection in detections:
            x, y, w, h = detection.bbox

            # Draw bounding box
            cv2.rectangle(
                output_frame,
                (x, y),
                (x + w, y + h),
                color,
                thickness
            )

            # Prepare label
            label_parts = []
            if show_class:
                label_parts.append(detection.class_name)
            if show_confidence:
                label_parts.append(f"{detection.confidence:.2f}")

            label = " ".join(label_parts)

            # Draw label background
            if label:
                (label_w, label_h), _ = cv2.getTextSize(
                    label,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    1
                )

                cv2.rectangle(
                    output_frame,
                    (x, y - label_h - 10),
                    (x + label_w + 10, y),
                    color,
                    -1
                )

                # Draw label text
                cv2.putText(
                    output_frame,
                    label,
                    (x + 5, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 0),
                    1
                )

        return output_frame

    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set confidence threshold.

        Args:
            threshold: New confidence threshold (0.0 - 1.0)
        """
        if 0.0 <= threshold <= 1.0:
            self.confidence_threshold = threshold
            logger.info(f"Confidence threshold set to {threshold}")
        else:
            logger.warning(f"Invalid confidence threshold: {threshold}")

    def set_iou_threshold(self, threshold: float) -> None:
        """
        Set IOU threshold for NMS.

        Args:
            threshold: New IOU threshold (0.0 - 1.0)
        """
        if 0.0 <= threshold <= 1.0:
            self.iou_threshold = threshold
            logger.info(f"IOU threshold set to {threshold}")
        else:
            logger.warning(f"Invalid IOU threshold: {threshold}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get detection statistics.

        Returns:
            Dictionary of statistics
        """
        avg_inference_time = (
            self.total_inference_time / self.frame_count
            if self.frame_count > 0
            else 0.0
        )

        avg_detections = (
            self.total_detections / self.frame_count
            if self.frame_count > 0
            else 0.0
        )

        fps = 1.0 / avg_inference_time if avg_inference_time > 0 else 0.0

        return {
            'total_frames': self.frame_count,
            'total_detections': self.total_detections,
            'avg_detections_per_frame': avg_detections,
            'total_inference_time': self.total_inference_time,
            'avg_inference_time': avg_inference_time,
            'inference_fps': fps,
            'model': self.model_name,
            'device': self.device,
            'confidence_threshold': self.confidence_threshold,
            'iou_threshold': self.iou_threshold
        }

    def reset_statistics(self) -> None:
        """Reset detection statistics."""
        self.total_detections = 0
        self.total_inference_time = 0.0
        self.frame_count = 0
        logger.info("Detection statistics reset")


if __name__ == "__main__":
    # Test detection engine
    config = {
        'detection': {
            'model': 'yolov8n.pt',
            'confidence_threshold': 0.5,
            'device': 'cuda',
            'target_classes': [0]
        }
    }

    engine = DetectionEngine(config)

    if engine.initialize():
        print("Detection engine initialized")

        # Create a test frame
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Run detection
        detections = engine.detect(test_frame)
        print(f"Detections: {len(detections)}")

        # Get statistics
        stats = engine.get_statistics()
        print(f"Statistics: {stats}")
