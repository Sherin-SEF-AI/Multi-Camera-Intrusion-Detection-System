"""
Advanced Anomaly Detection Engine
Machine learning-based anomaly detection using Isolation Forest and statistical methods.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import deque
import pickle
from pathlib import Path
import time

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from app.core.tracking_engine import Track
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AnomalyDetection:
    """Detected anomaly."""
    anomaly_type: str
    anomaly_score: float  # -1.0 to 1.0 (negative = anomaly)
    confidence: float  # 0.0 to 1.0
    track_id: int
    timestamp: float
    features: Dict[str, float]
    description: str


class FeatureExtractor:
    """
    Extract behavioral features from tracks for anomaly detection.
    """

    def __init__(self):
        """Initialize feature extractor."""
        self.logger = get_logger(__name__)

    def extract_features(
        self,
        track: Track,
        trajectory_history: Optional[List[Tuple[int, int, float]]] = None,
        zone_info: Optional[Dict] = None
    ) -> Dict[str, float]:
        """
        Extract feature vector from track.

        Features:
        - Speed (average, max, variance)
        - Direction changes
        - Bounding box aspect ratio
        - Bounding box size change rate
        - Trajectory straightness
        - Zone transitions
        - Dwell time
        - Movement patterns

        Args:
            track: Track object
            trajectory_history: Extended trajectory (x, y, timestamp)
            zone_info: Zone information

        Returns:
            Feature dictionary
        """
        features = {}

        # Basic track info
        x, y, w, h = track.bbox
        features['bbox_width'] = float(w)
        features['bbox_height'] = float(h)
        features['bbox_aspect_ratio'] = float(w) / max(h, 1)
        features['bbox_area'] = float(w * h)
        features['confidence'] = float(track.confidence)

        # Trajectory-based features
        if trajectory_history and len(trajectory_history) > 1:
            features.update(self._extract_trajectory_features(trajectory_history))
        elif len(track.trajectory) > 1:
            # Convert trajectory to history format
            history = [(x, y, time.time()) for x, y in track.trajectory]
            features.update(self._extract_trajectory_features(history))
        else:
            # Default values for insufficient trajectory
            features['speed_avg'] = 0.0
            features['speed_max'] = 0.0
            features['speed_variance'] = 0.0
            features['direction_changes'] = 0.0
            features['trajectory_straightness'] = 1.0
            features['acceleration_avg'] = 0.0

        # Zone-based features
        if zone_info:
            features['in_restricted_zone'] = 1.0 if zone_info.get('in_restricted', False) else 0.0
            features['zone_transitions'] = float(zone_info.get('transitions', 0))
            features['in_critical_zone'] = 1.0 if zone_info.get('criticality', 0) > 0.7 else 0.0
        else:
            features['in_restricted_zone'] = 0.0
            features['zone_transitions'] = 0.0
            features['in_critical_zone'] = 0.0

        # Track statistics
        features['track_age'] = float(track.age)
        features['track_hits'] = float(track.hits)

        return features

    def _extract_trajectory_features(
        self,
        trajectory: List[Tuple[int, int, float]]
    ) -> Dict[str, float]:
        """
        Extract features from trajectory.

        Args:
            trajectory: List of (x, y, timestamp) tuples

        Returns:
            Feature dictionary
        """
        features = {}

        if len(trajectory) < 2:
            return {
                'speed_avg': 0.0,
                'speed_max': 0.0,
                'speed_variance': 0.0,
                'direction_changes': 0.0,
                'trajectory_straightness': 1.0,
                'acceleration_avg': 0.0
            }

        # Calculate speeds
        speeds = []
        for i in range(1, len(trajectory)):
            x1, y1, t1 = trajectory[i - 1]
            x2, y2, t2 = trajectory[i]

            dt = t2 - t1
            if dt > 0:
                distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                speed = distance / dt  # pixels per second
                speeds.append(speed)

        if speeds:
            features['speed_avg'] = float(np.mean(speeds))
            features['speed_max'] = float(np.max(speeds))
            features['speed_variance'] = float(np.var(speeds))
        else:
            features['speed_avg'] = 0.0
            features['speed_max'] = 0.0
            features['speed_variance'] = 0.0

        # Calculate accelerations
        if len(speeds) > 1:
            accelerations = np.diff(speeds)
            features['acceleration_avg'] = float(np.mean(np.abs(accelerations)))
        else:
            features['acceleration_avg'] = 0.0

        # Calculate direction changes
        direction_changes = 0
        prev_dx, prev_dy = 0, 0

        for i in range(1, len(trajectory)):
            x1, y1, _ = trajectory[i - 1]
            x2, y2, _ = trajectory[i]

            dx = x2 - x1
            dy = y2 - y1

            if i > 1:
                # Calculate angle change
                dot_product = dx * prev_dx + dy * prev_dy
                if dot_product < 0:  # Direction changed significantly
                    direction_changes += 1

            prev_dx, prev_dy = dx, dy

        features['direction_changes'] = float(direction_changes)

        # Calculate trajectory straightness (0 = very curved, 1 = straight line)
        if len(trajectory) >= 3:
            x_coords = [p[0] for p in trajectory]
            y_coords = [p[1] for p in trajectory]

            # Distance from start to end
            straight_distance = np.sqrt(
                (x_coords[-1] - x_coords[0])**2 +
                (y_coords[-1] - y_coords[0])**2
            )

            # Total path length
            path_length = sum(
                np.sqrt((x_coords[i] - x_coords[i-1])**2 + (y_coords[i] - y_coords[i-1])**2)
                for i in range(1, len(trajectory))
            )

            straightness = straight_distance / max(path_length, 1.0)
            features['trajectory_straightness'] = float(straightness)
        else:
            features['trajectory_straightness'] = 1.0

        return features


class AnomalyDetector:
    """
    Machine learning-based anomaly detection.

    Uses Isolation Forest to detect unusual behavioral patterns
    that deviate from normal activity.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize anomaly detector.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        anomaly_config = self.config.get('anomaly_detection', {})

        self.enabled = anomaly_config.get('enabled', True) and SKLEARN_AVAILABLE
        self.contamination = anomaly_config.get('contamination', 0.1)  # Expected anomaly rate
        self.n_estimators = anomaly_config.get('n_estimators', 100)
        self.max_samples = anomaly_config.get('max_samples', 256)
        self.training_buffer_size = anomaly_config.get('training_buffer_size', 1000)
        self.retrain_interval = anomaly_config.get('retrain_interval', 300)  # seconds
        self.model_path = anomaly_config.get('model_path', 'models/anomaly_detector.pkl')

        # Feature extractor
        self.feature_extractor = FeatureExtractor()

        # Model components
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None

        # Training data buffer
        self.training_buffer = deque(maxlen=self.training_buffer_size)
        self.feature_names = []

        # Statistics
        self.last_train_time = 0
        self.total_predictions = 0
        self.total_anomalies = 0

        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available. Anomaly detection disabled.")
            logger.warning("Install with: pip install scikit-learn")
            self.enabled = False
        else:
            # Try to load existing model
            self._load_model()

            # Initialize new model if not loaded
            if self.model is None and self.enabled:
                self._initialize_model()

        logger.info(f"Anomaly Detector initialized (enabled={self.enabled})")

    def _initialize_model(self):
        """Initialize Isolation Forest model."""
        try:
            self.model = IsolationForest(
                contamination=self.contamination,
                n_estimators=self.n_estimators,
                max_samples=self.max_samples,
                random_state=42,
                n_jobs=-1  # Use all CPU cores
            )

            self.scaler = StandardScaler()

            logger.info("Isolation Forest model initialized")

        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            self.enabled = False

    def detect_anomaly(
        self,
        track: Track,
        trajectory_history: Optional[List[Tuple[int, int, float]]] = None,
        zone_info: Optional[Dict] = None
    ) -> Optional[AnomalyDetection]:
        """
        Detect anomalies in track behavior.

        Args:
            track: Track to analyze
            trajectory_history: Extended trajectory
            zone_info: Zone information

        Returns:
            AnomalyDetection if anomaly detected, None otherwise
        """
        if not self.enabled or self.model is None:
            return None

        try:
            # Extract features
            features = self.feature_extractor.extract_features(
                track,
                trajectory_history,
                zone_info
            )

            # Store feature names (first time)
            if not self.feature_names:
                self.feature_names = sorted(features.keys())

            # Convert to feature vector
            feature_vector = np.array([features[name] for name in self.feature_names])

            # Add to training buffer
            self.training_buffer.append(feature_vector)

            # Check if model needs retraining
            current_time = time.time()
            if current_time - self.last_train_time > self.retrain_interval:
                if len(self.training_buffer) >= 100:  # Minimum samples
                    self._retrain_model()

            # Predict anomaly
            feature_scaled = self.scaler.transform(feature_vector.reshape(1, -1))
            prediction = self.model.predict(feature_scaled)[0]
            anomaly_score = self.model.score_samples(feature_scaled)[0]

            self.total_predictions += 1

            # Anomaly detected (prediction = -1)
            if prediction == -1:
                self.total_anomalies += 1

                # Convert score to confidence (anomaly scores are negative)
                confidence = 1.0 - (1.0 / (1.0 + abs(anomaly_score)))

                # Determine anomaly type based on features
                anomaly_type = self._classify_anomaly_type(features)

                # Generate description
                description = self._generate_anomaly_description(features, anomaly_type)

                return AnomalyDetection(
                    anomaly_type=anomaly_type,
                    anomaly_score=anomaly_score,
                    confidence=confidence,
                    track_id=track.track_id,
                    timestamp=time.time(),
                    features=features,
                    description=description
                )

        except Exception as e:
            logger.error(f"Anomaly detection error: {e}")

        return None

    def _retrain_model(self):
        """Retrain the model with buffered data."""
        try:
            if len(self.training_buffer) < 100:
                return

            logger.info(f"Retraining model with {len(self.training_buffer)} samples...")

            # Convert buffer to array
            X = np.array(list(self.training_buffer))

            # Fit scaler
            self.scaler.fit(X)

            # Transform data
            X_scaled = self.scaler.transform(X)

            # Fit model
            self.model.fit(X_scaled)

            self.last_train_time = time.time()

            logger.info("Model retrained successfully")

            # Save model
            self._save_model()

        except Exception as e:
            logger.error(f"Model retraining failed: {e}")

    def _classify_anomaly_type(self, features: Dict[str, float]) -> str:
        """
        Classify the type of anomaly based on features.

        Args:
            features: Feature dictionary

        Returns:
            Anomaly type string
        """
        # High speed anomaly
        if features.get('speed_avg', 0) > 50.0:
            return "unusual_speed"

        # Erratic movement
        if features.get('direction_changes', 0) > 5:
            return "erratic_movement"

        # Unusual trajectory
        if features.get('trajectory_straightness', 1.0) < 0.3:
            return "unusual_trajectory"

        # Zone violation
        if features.get('in_restricted_zone', 0) > 0:
            return "zone_violation"

        # Unusual size
        bbox_area = features.get('bbox_area', 0)
        if bbox_area > 100000 or bbox_area < 1000:
            return "unusual_size"

        # High acceleration
        if features.get('acceleration_avg', 0) > 10.0:
            return "unusual_acceleration"

        return "general_anomaly"

    def _generate_anomaly_description(
        self,
        features: Dict[str, float],
        anomaly_type: str
    ) -> str:
        """
        Generate human-readable anomaly description.

        Args:
            features: Feature dictionary
            anomaly_type: Anomaly type

        Returns:
            Description string
        """
        if anomaly_type == "unusual_speed":
            return f"Unusually high speed: {features.get('speed_avg', 0):.1f} px/s"

        elif anomaly_type == "erratic_movement":
            changes = int(features.get('direction_changes', 0))
            return f"Erratic movement with {changes} direction changes"

        elif anomaly_type == "unusual_trajectory":
            straightness = features.get('trajectory_straightness', 1.0)
            return f"Unusual trajectory pattern (straightness: {straightness:.2f})"

        elif anomaly_type == "zone_violation":
            return "Detected in restricted zone"

        elif anomaly_type == "unusual_size":
            area = features.get('bbox_area', 0)
            return f"Unusual bounding box size: {area:.0f} px²"

        elif anomaly_type == "unusual_acceleration":
            accel = features.get('acceleration_avg', 0)
            return f"Unusual acceleration: {accel:.1f} px/s²"

        else:
            return "Behavioral anomaly detected"

    def _save_model(self):
        """Save model to disk."""
        try:
            model_path = Path(self.model_path)
            model_path.parent.mkdir(parents=True, exist_ok=True)

            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'config': {
                    'contamination': self.contamination,
                    'n_estimators': self.n_estimators,
                    'max_samples': self.max_samples
                }
            }

            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)

            logger.info(f"Model saved to {model_path}")

        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def _load_model(self):
        """Load model from disk."""
        try:
            model_path = Path(self.model_path)

            if not model_path.exists():
                logger.info("No existing model found")
                return

            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)

            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']

            logger.info(f"Model loaded from {model_path}")

        except Exception as e:
            logger.warning(f"Failed to load model: {e}")

    def get_statistics(self) -> Dict:
        """
        Get anomaly detection statistics.

        Returns:
            Statistics dictionary
        """
        anomaly_rate = 0.0
        if self.total_predictions > 0:
            anomaly_rate = self.total_anomalies / self.total_predictions

        return {
            'enabled': self.enabled,
            'total_predictions': self.total_predictions,
            'total_anomalies': self.total_anomalies,
            'anomaly_rate': anomaly_rate,
            'training_samples': len(self.training_buffer),
            'model_trained': self.model is not None,
            'last_train_time': self.last_train_time
        }


if __name__ == "__main__":
    # Test anomaly detector
    from app.core.detection_engine import Detection

    config = {
        'anomaly_detection': {
            'enabled': True,
            'contamination': 0.1,
            'n_estimators': 100,
            'max_samples': 256,
            'training_buffer_size': 1000,
            'retrain_interval': 60
        }
    }

    detector = AnomalyDetector(config)

    # Create mock track
    detection = Detection(
        bbox=(100, 100, 50, 100),
        confidence=0.9,
        class_id=0,
        class_name="person"
    )

    from app.core.tracking_engine import Track
    track = Track(
        track_id=1,
        bbox=detection.bbox,
        confidence=detection.confidence,
        class_id=detection.class_id,
        class_name=detection.class_name
    )

    # Simulate normal behavior
    print("Simulating normal behavior...")
    for i in range(50):
        track.bbox = (100 + i, 100, 50, 100)
        track.update(detection)

        anomaly = detector.detect_anomaly(track)
        if anomaly:
            print(f"Anomaly detected: {anomaly.description} (confidence: {anomaly.confidence:.2f})")

    # Simulate anomalous behavior (sudden speed change)
    print("\nSimulating anomalous behavior...")
    for i in range(10):
        track.bbox = (100 + i * 50, 100, 50, 100)  # Very fast movement
        track.update(detection)

        anomaly = detector.detect_anomaly(track)
        if anomaly:
            print(f"Anomaly detected: {anomaly.description} (confidence: {anomaly.confidence:.2f})")

    # Statistics
    stats = detector.get_statistics()
    print(f"\nStatistics: {stats}")

    print("Test complete")
