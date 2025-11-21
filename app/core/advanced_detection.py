"""
Advanced Object Detection Engine
Multi-class detection for vehicles, weapons, packages, fire/smoke, and more.
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import torch

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ObjectDetection:
    """Advanced object detection result."""
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    class_id: int
    class_name: str
    category: str  # person, vehicle, weapon, package, fire, etc.
    timestamp: datetime


class AdvancedDetectionEngine:
    """
    Advanced multi-class object detection engine.

    Supports detection of:
    - People (person)
    - Vehicles (car, truck, bus, motorcycle, bicycle)
    - Weapons (knife, gun - requires specialized model)
    - Packages/Objects (backpack, suitcase, handbag)
    - Animals (dog, cat, bird, etc.)
    - Fire/Smoke (requires specialized model)
    - Safety equipment (helmet, vest)
    """

    # COCO class names (YOLOv8 default)
    COCO_CLASSES = {
        0: 'person',
        1: 'bicycle',
        2: 'car',
        3: 'motorcycle',
        4: 'airplane',
        5: 'bus',
        6: 'train',
        7: 'truck',
        8: 'boat',
        14: 'bird',
        15: 'cat',
        16: 'dog',
        24: 'backpack',
        25: 'umbrella',
        26: 'handbag',
        27: 'tie',
        28: 'suitcase',
        39: 'bottle',
        41: 'cup',
        43: 'knife',
        44: 'spoon',
        45: 'bowl',
        56: 'chair',
        57: 'couch',
        62: 'laptop',
        63: 'mouse',
        64: 'remote',
        65: 'keyboard',
        66: 'cell phone',
        67: 'microwave',
        73: 'book',
        76: 'scissors',
        # ... more classes
    }

    # Category mapping
    CATEGORIES = {
        'person': [0],  # person
        'vehicle': [1, 2, 3, 5, 7],  # bicycle, car, motorcycle, bus, truck
        'package': [24, 26, 28],  # backpack, handbag, suitcase
        'weapon': [43, 76],  # knife, scissors (limited - needs specialized model)
        'animal': [14, 15, 16],  # bird, cat, dog
        'electronics': [62, 63, 64, 65, 66],  # laptop, mouse, remote, keyboard, cell phone
    }

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize advanced detection engine.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        detection_config = self.config.get('advanced_detection', {})

        self.enabled = detection_config.get('enabled', True) and YOLO_AVAILABLE
        self.model_path = detection_config.get('model', 'yolov8n.pt')
        self.confidence_threshold = detection_config.get('confidence_threshold', 0.5)
        self.device = detection_config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
        self.target_categories = detection_config.get('target_categories', ['person', 'vehicle', 'package'])

        self.model = None
        self.statistics = {
            'total_detections': 0,
            'detections_by_category': {},
            'inference_times': []
        }

        if not YOLO_AVAILABLE:
            logger.warning("Ultralytics YOLO not available. Advanced detection disabled.")
            self.enabled = False

        logger.info(f"Advanced Detection Engine initialized (enabled={self.enabled})")

    def initialize(self) -> bool:
        """
        Initialize the detection model.

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        try:
            logger.info(f"Loading model: {self.model_path}")
            self.model = YOLO(self.model_path)

            # Move to device
            if self.device == 'cuda' and torch.cuda.is_available():
                self.model.to('cuda')
                logger.info("Model loaded on GPU")
            else:
                logger.info("Model loaded on CPU")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize detection model: {e}")
            self.enabled = False
            return False

    def detect(
        self,
        frame: np.ndarray,
        categories: Optional[List[str]] = None
    ) -> List[ObjectDetection]:
        """
        Detect objects in frame.

        Args:
            frame: Input image (BGR format)
            categories: List of categories to detect (None = all configured)

        Returns:
            List of detections
        """
        if not self.enabled or self.model is None:
            return []

        try:
            import time
            start_time = time.time()

            # Run inference
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)

            # Filter categories
            target_cats = categories or self.target_categories
            target_class_ids = []
            for cat in target_cats:
                target_class_ids.extend(self.CATEGORIES.get(cat, []))

            detections = []

            for result in results:
                boxes = result.boxes

                for i in range(len(boxes)):
                    class_id = int(boxes.cls[i])

                    # Filter by target categories
                    if class_id not in target_class_ids:
                        continue

                    confidence = float(boxes.conf[i])

                    # Get bbox
                    x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                    bbox = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))

                    # Get class name
                    class_name = self.COCO_CLASSES.get(class_id, f"class_{class_id}")

                    # Determine category
                    category = self._get_category(class_id)

                    detection = ObjectDetection(
                        bbox=bbox,
                        confidence=confidence,
                        class_id=class_id,
                        class_name=class_name,
                        category=category,
                        timestamp=datetime.now()
                    )

                    detections.append(detection)

                    # Update statistics
                    self.statistics['total_detections'] += 1
                    self.statistics['detections_by_category'][category] = \
                        self.statistics['detections_by_category'].get(category, 0) + 1

            # Track inference time
            inference_time = time.time() - start_time
            self.statistics['inference_times'].append(inference_time)

            # Keep only last 100 inference times
            if len(self.statistics['inference_times']) > 100:
                self.statistics['inference_times'].pop(0)

            return detections

        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def _get_category(self, class_id: int) -> str:
        """
        Get category for class ID.

        Args:
            class_id: COCO class ID

        Returns:
            Category name
        """
        for category, class_ids in self.CATEGORIES.items():
            if class_id in class_ids:
                return category

        return "other"

    def detect_vehicles(self, frame: np.ndarray) -> List[ObjectDetection]:
        """
        Detect vehicles only.

        Args:
            frame: Input image

        Returns:
            List of vehicle detections
        """
        return self.detect(frame, categories=['vehicle'])

    def detect_packages(self, frame: np.ndarray) -> List[ObjectDetection]:
        """
        Detect packages/bags only.

        Args:
            frame: Input image

        Returns:
            List of package detections
        """
        return self.detect(frame, categories=['package'])

    def detect_left_objects(
        self,
        current_detections: List[ObjectDetection],
        previous_detections: List[ObjectDetection],
        stationary_threshold: int = 30
    ) -> List[ObjectDetection]:
        """
        Detect stationary/left objects (abandoned packages, etc.).

        Args:
            current_detections: Current frame detections
            previous_detections: Previous frame detections
            stationary_threshold: Frames to consider object as left

        Returns:
            List of potentially left objects
        """
        # Simple implementation: packages that appear in same location
        # This is a placeholder - full implementation would track objects over time

        left_objects = []

        for curr_det in current_detections:
            if curr_det.category != 'package':
                continue

            # Check if similar detection in previous frame
            for prev_det in previous_detections:
                if prev_det.category != 'package':
                    continue

                # Check if same location (rough IoU)
                iou = self._calculate_iou(curr_det.bbox, prev_det.bbox)

                if iou > 0.5:
                    # Potentially stationary object
                    left_objects.append(curr_det)
                    break

        return left_objects

    def _calculate_iou(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> float:
        """
        Calculate Intersection over Union.

        Args:
            bbox1: First bounding box (x, y, w, h)
            bbox2: Second bounding box (x, y, w, h)

        Returns:
            IoU value (0.0 to 1.0)
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        # Convert to (x1, y1, x2, y2)
        box1 = [x1, y1, x1 + w1, y1 + h1]
        box2 = [x2, y2, x2 + w2, y2 + h2]

        # Calculate intersection
        xi1 = max(box1[0], box2[0])
        yi1 = max(box1[1], box2[1])
        xi2 = min(box1[2], box2[2])
        yi2 = min(box1[3], box2[3])

        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)

        # Calculate union
        box1_area = w1 * h1
        box2_area = w2 * h2
        union_area = box1_area + box2_area - inter_area

        # Calculate IoU
        iou = inter_area / union_area if union_area > 0 else 0.0

        return iou

    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[ObjectDetection],
        show_confidence: bool = True
    ) -> np.ndarray:
        """
        Draw detections on frame.

        Args:
            frame: Input image
            detections: List of detections
            show_confidence: Show confidence scores

        Returns:
            Annotated frame
        """
        output = frame.copy()

        # Category colors
        colors = {
            'person': (0, 255, 0),      # Green
            'vehicle': (255, 0, 0),     # Blue
            'package': (0, 255, 255),   # Yellow
            'weapon': (0, 0, 255),      # Red
            'animal': (255, 255, 0),    # Cyan
            'other': (128, 128, 128)    # Gray
        }

        for detection in detections:
            x, y, w, h = detection.bbox
            color = colors.get(detection.category, (128, 128, 128))

            # Draw rectangle
            cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)

            # Draw label
            label = f"{detection.class_name}"
            if show_confidence:
                label += f" {detection.confidence:.2f}"

            # Background for text
            (text_width, text_height), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )

            cv2.rectangle(
                output,
                (x, y - text_height - 5),
                (x + text_width, y),
                color,
                -1
            )

            # Text
            cv2.putText(
                output,
                label,
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        return output

    def get_statistics(self) -> Dict:
        """
        Get detection statistics.

        Returns:
            Statistics dictionary
        """
        avg_inference_time = 0.0
        if self.statistics['inference_times']:
            avg_inference_time = np.mean(self.statistics['inference_times'])

        return {
            'enabled': self.enabled,
            'total_detections': self.statistics['total_detections'],
            'detections_by_category': self.statistics['detections_by_category'].copy(),
            'avg_inference_time': avg_inference_time,
            'inference_fps': 1.0 / avg_inference_time if avg_inference_time > 0 else 0.0
        }


if __name__ == "__main__":
    # Test advanced detection
    print("Testing Advanced Detection Engine...")

    config = {
        'advanced_detection': {
            'enabled': True,
            'model': 'yolov8n.pt',
            'confidence_threshold': 0.5,
            'device': 'cpu',
            'target_categories': ['person', 'vehicle', 'package']
        }
    }

    engine = AdvancedDetectionEngine(config)

    if engine.initialize():
        print("Engine initialized successfully")

        # Create test image
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Detect objects
        detections = engine.detect(test_frame)
        print(f"Detected {len(detections)} objects")

        # Get statistics
        stats = engine.get_statistics()
        print(f"Statistics: {stats}")
    else:
        print("Engine initialization failed")

    print("\nAdvanced Detection Test Complete!")
