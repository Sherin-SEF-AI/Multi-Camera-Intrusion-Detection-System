"""
Crowd Analytics Engine
Advanced people counting, density analysis, and crowd behavior monitoring.
"""

import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import time

from app.core.tracking_engine import Track
from app.core.detection_engine import Detection
from app.database.models import PeopleCount
from app.database.database_manager import DatabaseManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CrowdMetrics:
    """Crowd analysis metrics."""
    camera_id: int
    timestamp: datetime
    people_count: int
    density: float  # People per square meter
    density_level: str  # Low, Medium, High, Critical
    flow_rate: float  # People per minute
    dwell_time_avg: float  # Average seconds
    social_distance_violations: int
    crowd_behavior: str  # Normal, Gathering, Dispersing, Panic


@dataclass
class HeatmapPoint:
    """Point in occupancy heatmap."""
    x: int
    y: int
    intensity: float  # 0.0 to 1.0


class CrowdAnalytics:
    """
    Advanced crowd analytics engine.

    Features:
    - Real-time people counting
    - Crowd density estimation
    - Flow rate analysis (entry/exit counting)
    - Social distancing monitoring
    - Occupancy heatmaps
    - Crowd behavior detection
    - Queue management
    - Dwell time analysis
    """

    def __init__(self, database: DatabaseManager, config: Optional[dict] = None):
        """
        Initialize crowd analytics.

        Args:
            database: Database manager
            config: Configuration dictionary
        """
        self.database = database
        self.config = config or {}
        crowd_config = self.config.get('crowd_analytics', {})

        # Configuration
        self.enabled = crowd_config.get('enabled', True)
        self.area_size_sqm = crowd_config.get('area_size_sqm', 100.0)  # Square meters
        self.social_distance_threshold = crowd_config.get('social_distance_m', 2.0)  # Meters
        self.density_thresholds = crowd_config.get('density_thresholds', {
            'low': 0.1,     # < 0.1 people/m²
            'medium': 0.3,  # 0.1-0.3 people/m²
            'high': 0.5,    # 0.3-0.5 people/m²
            'critical': 0.5  # > 0.5 people/m²
        })

        # Per-camera data
        self.camera_counts: Dict[int, int] = {}
        self.entry_zones: Dict[int, List[Tuple[int, int, int, int]]] = {}  # camera_id -> bbox list
        self.exit_zones: Dict[int, List[Tuple[int, int, int, int]]] = {}
        self.count_history: Dict[int, deque] = {}  # Rolling window of counts
        self.track_entry_time: Dict[int, float] = {}  # track_id -> entry timestamp

        # Heatmap data
        self.heatmap_resolution = crowd_config.get('heatmap_resolution', (50, 50))
        self.heatmaps: Dict[int, np.ndarray] = {}  # camera_id -> heatmap
        self.heatmap_decay = crowd_config.get('heatmap_decay', 0.95)  # Decay factor per update

        # Statistics
        self.total_counts = 0

        logger.info("Crowd Analytics initialized")

    def update(
        self,
        camera_id: int,
        tracks: List[Track],
        frame_shape: Tuple[int, int] = (720, 1280)
    ) -> CrowdMetrics:
        """
        Update crowd analytics for a camera frame.

        Args:
            camera_id: Camera ID
            tracks: Active tracks in frame
            frame_shape: Frame dimensions (height, width)

        Returns:
            CrowdMetrics for current frame
        """
        # Count people
        people_count = len(tracks)
        self.camera_counts[camera_id] = people_count
        self.total_counts += 1

        # Initialize history if needed
        if camera_id not in self.count_history:
            self.count_history[camera_id] = deque(maxlen=300)  # 10 seconds at 30 FPS

        self.count_history[camera_id].append((time.time(), people_count))

        # Calculate density
        density = self._calculate_density(people_count)
        density_level = self._classify_density(density)

        # Calculate flow rate
        flow_rate = self._calculate_flow_rate(camera_id)

        # Analyze dwell times
        dwell_time_avg = self._calculate_avg_dwell_time(tracks)

        # Check social distancing
        violations = self._check_social_distancing(tracks)

        # Detect crowd behavior
        behavior = self._detect_crowd_behavior(camera_id, people_count)

        # Update heatmap
        self._update_heatmap(camera_id, tracks, frame_shape)

        # Store in database
        self._store_count(camera_id, people_count)

        metrics = CrowdMetrics(
            camera_id=camera_id,
            timestamp=datetime.now(),
            people_count=people_count,
            density=density,
            density_level=density_level,
            flow_rate=flow_rate,
            dwell_time_avg=dwell_time_avg,
            social_distance_violations=violations,
            crowd_behavior=behavior
        )

        return metrics

    def _calculate_density(self, people_count: int) -> float:
        """
        Calculate crowd density.

        Args:
            people_count: Number of people

        Returns:
            Density in people per square meter
        """
        return people_count / self.area_size_sqm

    def _classify_density(self, density: float) -> str:
        """
        Classify density level.

        Args:
            density: Density value

        Returns:
            Level string (Low, Medium, High, Critical)
        """
        thresholds = self.density_thresholds

        if density < thresholds['low']:
            return "Low"
        elif density < thresholds['medium']:
            return "Medium"
        elif density < thresholds['high']:
            return "High"
        else:
            return "Critical"

    def _calculate_flow_rate(self, camera_id: int) -> float:
        """
        Calculate people flow rate (people per minute).

        Args:
            camera_id: Camera ID

        Returns:
            Flow rate
        """
        if camera_id not in self.count_history:
            return 0.0

        history = self.count_history[camera_id]

        if len(history) < 2:
            return 0.0

        # Get counts from last minute
        current_time = time.time()
        one_minute_ago = current_time - 60

        recent_counts = [count for timestamp, count in history if timestamp > one_minute_ago]

        if not recent_counts:
            return 0.0

        # Average change rate
        flow_rate = (max(recent_counts) - min(recent_counts)) / 1.0  # per minute

        return max(0.0, flow_rate)

    def _calculate_avg_dwell_time(self, tracks: List[Track]) -> float:
        """
        Calculate average dwell time.

        Args:
            tracks: Active tracks

        Returns:
            Average dwell time in seconds
        """
        if not tracks:
            return 0.0

        current_time = time.time()
        dwell_times = []

        for track in tracks:
            # Track entry time
            if track.track_id not in self.track_entry_time:
                self.track_entry_time[track.track_id] = current_time

            entry_time = self.track_entry_time[track.track_id]
            dwell_time = current_time - entry_time
            dwell_times.append(dwell_time)

        return np.mean(dwell_times) if dwell_times else 0.0

    def _check_social_distancing(self, tracks: List[Track]) -> int:
        """
        Check social distancing violations.

        Args:
            tracks: Active tracks

        Returns:
            Number of violations
        """
        if len(tracks) < 2:
            return 0

        violations = 0

        # Check pairwise distances
        for i in range(len(tracks)):
            for j in range(i + 1, len(tracks)):
                track1 = tracks[i]
                track2 = tracks[j]

                # Get center points
                x1, y1, w1, h1 = track1.bbox
                x2, y2, w2, h2 = track2.bbox

                center1 = (x1 + w1 / 2, y1 + h1 / 2)
                center2 = (x2 + w2 / 2, y2 + h2 / 2)

                # Calculate Euclidean distance in pixels
                distance_px = np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)

                # Convert to meters (rough estimate: assume 1 meter ≈ 100 pixels)
                # This should be calibrated per camera
                distance_m = distance_px / 100.0

                if distance_m < self.social_distance_threshold:
                    violations += 1

        return violations

    def _detect_crowd_behavior(self, camera_id: int, current_count: int) -> str:
        """
        Detect crowd behavior pattern.

        Args:
            camera_id: Camera ID
            current_count: Current people count

        Returns:
            Behavior classification
        """
        if camera_id not in self.count_history:
            return "Normal"

        history = self.count_history[camera_id]

        if len(history) < 10:
            return "Normal"

        # Get recent counts
        recent_counts = [count for _, count in list(history)[-30:]]

        if not recent_counts:
            return "Normal"

        # Calculate trend
        avg_count = np.mean(recent_counts)
        trend = current_count - avg_count

        # Classify behavior
        if abs(trend) < 2:
            return "Normal"
        elif trend > 5:
            return "Gathering"
        elif trend < -5:
            return "Dispersing"
        elif len(recent_counts) > 5:
            # Check for rapid changes (panic)
            std_dev = np.std(recent_counts)
            if std_dev > 10:
                return "Panic"

        return "Normal"

    def _update_heatmap(
        self,
        camera_id: int,
        tracks: List[Track],
        frame_shape: Tuple[int, int]
    ):
        """
        Update occupancy heatmap.

        Args:
            camera_id: Camera ID
            tracks: Active tracks
            frame_shape: Frame dimensions (height, width)
        """
        height, width = frame_shape
        hmap_h, hmap_w = self.heatmap_resolution

        # Initialize heatmap if needed
        if camera_id not in self.heatmaps:
            self.heatmaps[camera_id] = np.zeros((hmap_h, hmap_w), dtype=np.float32)

        # Decay existing heatmap
        self.heatmaps[camera_id] *= self.heatmap_decay

        # Add current detections
        for track in tracks:
            x, y, w, h = track.bbox

            # Calculate center
            center_x = int((x + w / 2) / width * hmap_w)
            center_y = int((y + h / 2) / height * hmap_h)

            # Clip to heatmap bounds
            center_x = max(0, min(hmap_w - 1, center_x))
            center_y = max(0, min(hmap_h - 1, center_y))

            # Add to heatmap with Gaussian-like spread
            self.heatmaps[camera_id][center_y, center_x] += 1.0

            # Spread to neighbors
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = center_y + dy, center_x + dx
                    if 0 <= ny < hmap_h and 0 <= nx < hmap_w:
                        distance = np.sqrt(dx**2 + dy**2)
                        if distance > 0:
                            self.heatmaps[camera_id][ny, nx] += 0.3 / distance

        # Normalize
        max_val = self.heatmaps[camera_id].max()
        if max_val > 0:
            self.heatmaps[camera_id] /= max_val

    def get_heatmap(self, camera_id: int) -> Optional[np.ndarray]:
        """
        Get occupancy heatmap for camera.

        Args:
            camera_id: Camera ID

        Returns:
            Heatmap as numpy array (values 0.0-1.0)
        """
        return self.heatmaps.get(camera_id)

    def get_heatmap_visualization(
        self,
        camera_id: int,
        frame_shape: Tuple[int, int]
    ) -> Optional[np.ndarray]:
        """
        Get heatmap visualization overlay.

        Args:
            camera_id: Camera ID
            frame_shape: Original frame shape (height, width)

        Returns:
            Colored heatmap overlay
        """
        heatmap = self.get_heatmap(camera_id)

        if heatmap is None:
            return None

        # Resize to frame size
        resized = cv2.resize(heatmap, (frame_shape[1], frame_shape[0]))

        # Apply colormap
        heatmap_colored = cv2.applyColorMap(
            (resized * 255).astype(np.uint8),
            cv2.COLORMAP_JET
        )

        return heatmap_colored

    def _store_count(self, camera_id: int, count: int):
        """
        Store count in database.

        Args:
            camera_id: Camera ID
            count: People count
        """
        try:
            people_count = PeopleCount(
                camera_id=camera_id,
                count=count,
                timestamp=datetime.now()
            )

            self.database.add(people_count)

        except Exception as e:
            logger.error(f"Failed to store people count: {e}")

    def get_statistics(self, camera_id: Optional[int] = None, hours: int = 24) -> Dict:
        """
        Get crowd analytics statistics.

        Args:
            camera_id: Camera ID (None for all cameras)
            hours: Time period in hours

        Returns:
            Statistics dictionary
        """
        try:
            start_time = datetime.now() - timedelta(hours=hours)

            with self.database.session_scope() as session:
                query = session.query(PeopleCount).filter(
                    PeopleCount.timestamp >= start_time
                )

                if camera_id is not None:
                    query = query.filter(PeopleCount.camera_id == camera_id)

                counts = query.all()

                if not counts:
                    return {'total_counts': 0}

                count_values = [c.count for c in counts]

                return {
                    'total_counts': len(counts),
                    'avg_count': np.mean(count_values),
                    'max_count': max(count_values),
                    'min_count': min(count_values),
                    'current_count': self.camera_counts.get(camera_id, 0) if camera_id else sum(self.camera_counts.values()),
                    'period_hours': hours
                }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}


if __name__ == "__main__":
    # Test crowd analytics
    print("Testing Crowd Analytics...")

    # Mock data
    from app.core.detection_engine import Detection
    from app.core.tracking_engine import Track

    # Create mock tracks
    tracks = []
    for i in range(15):
        det = Detection(
            bbox=(100 + i * 50, 100, 40, 100),
            confidence=0.9,
            class_id=0,
            class_name="person"
        )
        track = Track(
            track_id=i,
            bbox=det.bbox,
            confidence=det.confidence,
            class_id=det.class_id,
            class_name=det.class_name
        )
        tracks.append(track)

    # Mock database
    class MockDB:
        def add(self, obj):
            pass

    analytics = CrowdAnalytics(MockDB())
    metrics = analytics.update(camera_id=0, tracks=tracks, frame_shape=(720, 1280))

    print(f"People Count: {metrics.people_count}")
    print(f"Density: {metrics.density:.3f} people/m²")
    print(f"Density Level: {metrics.density_level}")
    print(f"Flow Rate: {metrics.flow_rate:.1f} people/min")
    print(f"Avg Dwell Time: {metrics.dwell_time_avg:.1f}s")
    print(f"Social Distance Violations: {metrics.social_distance_violations}")
    print(f"Crowd Behavior: {metrics.crowd_behavior}")

    print("\nCrowd Analytics Test Complete!")
