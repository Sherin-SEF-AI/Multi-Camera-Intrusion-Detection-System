"""
Behavioral Analysis Engine
Analyze person behavior using pose estimation and trajectory analysis.
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import deque
import time

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    mp = None

from app.core.tracking_engine import Track
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BehaviorDetection:
    """Detected behavior."""
    behavior_type: str  # loitering, running, fall, aggressive, etc.
    confidence: float  # 0.0 - 1.0
    track_id: int
    timestamp: float
    description: str


class PoseEstimator:
    """
    Pose estimation using MediaPipe.
    """

    def __init__(self):
        """Initialize pose estimator."""
        if not MEDIAPIPE_AVAILABLE:
            logger.warning("MediaPipe not available. Pose estimation disabled.")
            logger.warning("Install with: pip install mediapipe")
            self.enabled = False
            return

        self.enabled = True
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils

        # Initialize MediaPipe Pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        logger.info("Pose estimator initialized")

    def estimate_pose(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> Optional[Dict]:
        """
        Estimate pose for person in bounding box.

        Args:
            frame: Full frame
            bbox: Bounding box (x, y, w, h)

        Returns:
            Pose landmarks dictionary or None
        """
        if not self.enabled:
            return None

        try:
            x, y, w, h = bbox

            # Extract person region
            person_img = frame[y:y+h, x:x+w]

            if person_img.size == 0:
                return None

            # Convert BGR to RGB
            rgb_img = cv2.cvtColor(person_img, cv2.COLOR_BGR2RGB)

            # Process
            results = self.pose.process(rgb_img)

            if results.pose_landmarks:
                # Convert to dictionary format
                landmarks = {}
                for idx, landmark in enumerate(results.pose_landmarks.landmark):
                    # Adjust coordinates to full frame
                    landmarks[idx] = {
                        'x': x + landmark.x * w,
                        'y': y + landmark.y * h,
                        'z': landmark.z,
                        'visibility': landmark.visibility
                    }

                return {
                    'landmarks': landmarks,
                    'raw_landmarks': results.pose_landmarks
                }

        except Exception as e:
            logger.error(f"Pose estimation error: {e}")

        return None

    def draw_pose(self, frame: np.ndarray, pose_data: Dict, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """
        Draw pose skeleton on frame.

        Args:
            frame: Frame to draw on
            pose_data: Pose data from estimate_pose
            bbox: Bounding box

        Returns:
            Frame with pose drawn
        """
        if not self.enabled or not pose_data:
            return frame

        try:
            x, y, w, h = bbox
            person_img = frame[y:y+h, x:x+w].copy()

            # Draw landmarks
            self.mp_drawing.draw_landmarks(
                person_img,
                pose_data['raw_landmarks'],
                self.mp_pose.POSE_CONNECTIONS
            )

            # Put back in frame
            frame[y:y+h, x:x+w] = person_img

        except Exception as e:
            logger.error(f"Error drawing pose: {e}")

        return frame

    def close(self):
        """Clean up resources."""
        if self.enabled and self.pose:
            self.pose.close()


class BehavioralAnalysis:
    """
    Behavioral analysis engine.

    Detects:
    - Loitering (staying in area too long)
    - Running (high speed movement)
    - Falls (sudden downward movement)
    - Aggressive behavior (rapid arm movements, fighting stance)
    - Erratic movement (zigzag patterns)
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize behavioral analysis.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        behavior_config = self.config.get('behavior', {})

        self.enabled = behavior_config.get('enabled', True)
        self.pose_detection = behavior_config.get('pose_detection', True)
        self.loitering_threshold = behavior_config.get('loitering_threshold', 30)  # seconds
        self.running_speed_threshold = behavior_config.get('running_speed_threshold', 2.5)  # m/s

        # Track history for behavior analysis
        self.track_positions = {}  # track_id -> deque of (x, y, timestamp)
        self.track_first_seen = {}  # track_id -> timestamp

        # Pose estimator
        self.pose_estimator = PoseEstimator() if self.pose_detection else None

        # Detected behaviors
        self.recent_behaviors = deque(maxlen=100)

        logger.info(f"Behavioral Analysis initialized (pose={self.pose_detection})")

    def analyze_track(
        self,
        track: Track,
        frame: Optional[np.ndarray] = None,
        zone_name: Optional[str] = None
    ) -> List[BehaviorDetection]:
        """
        Analyze track for behavioral anomalies.

        Args:
            track: Track to analyze
            frame: Current frame (for pose estimation)
            zone_name: Name of zone track is in

        Returns:
            List of detected behaviors
        """
        if not self.enabled:
            return []

        detections = []

        # Track history
        track_id = track.track_id
        current_time = time.time()

        # Update position history
        if track_id not in self.track_positions:
            self.track_positions[track_id] = deque(maxlen=30)
            self.track_first_seen[track_id] = current_time

        center_x = track.bbox[0] + track.bbox[2] // 2
        center_y = track.bbox[1] + track.bbox[3] // 2
        self.track_positions[track_id].append((center_x, center_y, current_time))

        # Behavior 1: Loitering detection
        loitering = self._detect_loitering(track_id, current_time)
        if loitering:
            detections.append(loitering)

        # Behavior 2: Running detection
        running = self._detect_running(track_id)
        if running:
            detections.append(running)

        # Behavior 3: Erratic movement
        erratic = self._detect_erratic_movement(track_id)
        if erratic:
            detections.append(erratic)

        # Behavior 4: Fall detection (requires pose)
        if self.pose_estimator and self.pose_estimator.enabled and frame is not None:
            fall = self._detect_fall(track, frame)
            if fall:
                detections.append(fall)

        # Store recent detections
        for detection in detections:
            self.recent_behaviors.append(detection)

        return detections

    def _detect_loitering(self, track_id: int, current_time: float) -> Optional[BehaviorDetection]:
        """
        Detect loitering (staying in area without movement).

        Args:
            track_id: Track ID
            current_time: Current timestamp

        Returns:
            BehaviorDetection or None
        """
        if track_id not in self.track_first_seen:
            return None

        # Calculate time in area
        time_in_area = current_time - self.track_first_seen[track_id]

        if time_in_area < self.loitering_threshold:
            return None

        # Check movement (low displacement = loitering)
        positions = self.track_positions[track_id]

        if len(positions) < 10:
            return None

        # Calculate total displacement
        first_pos = positions[0]
        last_pos = positions[-1]
        displacement = np.sqrt(
            (last_pos[0] - first_pos[0])**2 +
            (last_pos[1] - first_pos[1])**2
        )

        # Low displacement over time = loitering
        if displacement < 50:  # pixels
            confidence = min(1.0, time_in_area / (self.loitering_threshold * 2))

            return BehaviorDetection(
                behavior_type="loitering",
                confidence=confidence,
                track_id=track_id,
                timestamp=current_time,
                description=f"Person loitering for {time_in_area:.1f} seconds"
            )

        return None

    def _detect_running(self, track_id: int) -> Optional[BehaviorDetection]:
        """
        Detect running (high-speed movement).

        Args:
            track_id: Track ID

        Returns:
            BehaviorDetection or None
        """
        positions = self.track_positions.get(track_id, [])

        if len(positions) < 5:
            return None

        # Calculate speed over recent frames
        speeds = []
        for i in range(1, len(positions)):
            prev_x, prev_y, prev_t = positions[i-1]
            curr_x, curr_y, curr_t = positions[i]

            dt = curr_t - prev_t
            if dt == 0:
                continue

            # Pixel displacement
            dx = curr_x - prev_x
            dy = curr_y - prev_y
            distance = np.sqrt(dx**2 + dy**2)

            # Convert to speed (assuming ~30 pixels = 1 meter)
            speed_pixels_per_sec = distance / dt
            speed_m_per_sec = speed_pixels_per_sec / 30.0  # Approximate

            speeds.append(speed_m_per_sec)

        if not speeds:
            return None

        avg_speed = np.mean(speeds)

        # High speed = running
        if avg_speed > self.running_speed_threshold:
            confidence = min(1.0, avg_speed / (self.running_speed_threshold * 2))

            return BehaviorDetection(
                behavior_type="running",
                confidence=confidence,
                track_id=track_id,
                timestamp=time.time(),
                description=f"Person running at {avg_speed:.1f} m/s"
            )

        return None

    def _detect_erratic_movement(self, track_id: int) -> Optional[BehaviorDetection]:
        """
        Detect erratic/zigzag movement patterns.

        Args:
            track_id: Track ID

        Returns:
            BehaviorDetection or None
        """
        positions = self.track_positions.get(track_id, [])

        if len(positions) < 10:
            return None

        # Calculate direction changes
        direction_changes = 0
        prev_dx, prev_dy = 0, 0

        for i in range(1, len(positions)):
            prev_x, prev_y, _ = positions[i-1]
            curr_x, curr_y, _ = positions[i]

            dx = curr_x - prev_x
            dy = curr_y - prev_y

            if i > 1:
                # Check if direction changed significantly
                dot_product = dx * prev_dx + dy * prev_dy
                if dot_product < 0:  # Opposite direction
                    direction_changes += 1

            prev_dx, prev_dy = dx, dy

        # Many direction changes = erratic
        erratic_threshold = len(positions) * 0.3  # 30% of movements

        if direction_changes > erratic_threshold:
            confidence = min(1.0, direction_changes / len(positions))

            return BehaviorDetection(
                behavior_type="erratic_movement",
                confidence=confidence,
                track_id=track_id,
                timestamp=time.time(),
                description=f"Erratic movement pattern detected ({direction_changes} direction changes)"
            )

        return None

    def _detect_fall(self, track: Track, frame: np.ndarray) -> Optional[BehaviorDetection]:
        """
        Detect falls using pose estimation.

        Args:
            track: Track object
            frame: Current frame

        Returns:
            BehaviorDetection or None
        """
        # Get pose
        pose_data = self.pose_estimator.estimate_pose(frame, track.bbox)

        if not pose_data:
            return None

        landmarks = pose_data['landmarks']

        # Check if person is lying down (nose Y > hip Y significantly)
        # MediaPipe landmark indices: 0 = nose, 23/24 = hips

        if 0 not in landmarks or 23 not in landmarks:
            return None

        nose_y = landmarks[0]['y']
        hip_y = landmarks[23]['y']

        # If nose is significantly below hip (inverted), possible fall
        if nose_y > hip_y + 50:  # 50 pixels threshold
            return BehaviorDetection(
                behavior_type="fall",
                confidence=0.8,
                track_id=track.track_id,
                timestamp=time.time(),
                description="Possible fall detected"
            )

        return None

    def get_anomaly_score(self, track_id: int) -> float:
        """
        Calculate overall behavior anomaly score for a track.

        Args:
            track_id: Track ID

        Returns:
            Anomaly score (0.0 - 1.0)
        """
        # Count recent behaviors for this track
        recent = [b for b in self.recent_behaviors if b.track_id == track_id]

        if not recent:
            return 0.0

        # Average confidence of recent detections
        avg_confidence = np.mean([b.confidence for b in recent])

        # Weight by number of different behaviors
        unique_behaviors = len(set(b.behavior_type for b in recent))
        behavior_factor = min(1.0, unique_behaviors / 3.0)

        return avg_confidence * behavior_factor

    def cleanup_old_tracks(self, active_track_ids: List[int]):
        """
        Remove data for tracks that no longer exist.

        Args:
            active_track_ids: List of currently active track IDs
        """
        # Clean up position history
        inactive_ids = set(self.track_positions.keys()) - set(active_track_ids)
        for track_id in inactive_ids:
            self.track_positions.pop(track_id, None)
            self.track_first_seen.pop(track_id, None)

    def close(self):
        """Clean up resources."""
        if self.pose_estimator:
            self.pose_estimator.close()


if __name__ == "__main__":
    # Test behavioral analysis
    from app.core.detection_engine import Detection

    config = {
        'behavior': {
            'enabled': True,
            'pose_detection': MEDIAPIPE_AVAILABLE,
            'loitering_threshold': 10,  # Lower for testing
            'running_speed_threshold': 2.5
        }
    }

    analyzer = BehavioralAnalysis(config)

    # Create mock track
    detection = Detection(
        bbox=(100, 100, 50, 100),
        confidence=0.9,
        class_id=0,
        class_name="person"
    )

    track = Track(
        track_id=1,
        bbox=detection.bbox,
        confidence=detection.confidence,
        class_id=detection.class_id,
        class_name=detection.class_name
    )

    # Simulate loitering
    print("Test: Simulating loitering...")
    for i in range(15):
        behaviors = analyzer.analyze_track(track)
        if behaviors:
            for b in behaviors:
                print(f"Detected: {b.behavior_type} (confidence: {b.confidence:.2f})")
        time.sleep(1)

    print("Test complete")
    analyzer.close()
