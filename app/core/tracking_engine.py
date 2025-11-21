"""
Tracking Engine
Multi-object tracking system for person tracking across frames.
Implements simplified ByteTrack-style tracking.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import time

from app.core.detection_engine import Detection
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Track:
    """Represents a tracked object."""
    track_id: int
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    class_id: int
    class_name: str
    age: int = 0  # Frames since last update
    hits: int = 0  # Total number of detections
    time_since_update: int = 0
    state: str = "tentative"  # tentative, confirmed, deleted
    trajectory: deque = field(default_factory=lambda: deque(maxlen=30))
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def __post_init__(self):
        """Initialize trajectory with first position."""
        center_x = self.bbox[0] + self.bbox[2] // 2
        center_y = self.bbox[1] + self.bbox[3] // 2
        self.trajectory.append((center_x, center_y))

    def update(self, detection: Detection):
        """Update track with new detection."""
        self.bbox = detection.bbox
        self.confidence = detection.confidence
        self.hits += 1
        self.time_since_update = 0
        self.last_seen = time.time()

        # Update trajectory
        center_x = self.bbox[0] + self.bbox[2] // 2
        center_y = self.bbox[1] + self.bbox[3] // 2
        self.trajectory.append((center_x, center_y))

        # Confirm track after minimum hits
        if self.state == "tentative" and self.hits >= 3:
            self.state = "confirmed"

    def predict(self):
        """Predict next state (placeholder for Kalman filter)."""
        self.age += 1
        self.time_since_update += 1


def compute_iou(bbox1: Tuple[int, int, int, int], bbox2: Tuple[int, int, int, int]) -> float:
    """
    Compute Intersection over Union (IoU) between two bounding boxes.

    Args:
        bbox1: First bounding box (x, y, w, h)
        bbox2: Second bounding box (x, y, w, h)

    Returns:
        IoU value (0.0 - 1.0)
    """
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2

    # Convert to (x1, y1, x2, y2) format
    box1 = [x1, y1, x1 + w1, y1 + h1]
    box2 = [x2, y2, x2 + w2, y2 + h2]

    # Compute intersection
    inter_x1 = max(box1[0], box2[0])
    inter_y1 = max(box1[1], box2[1])
    inter_x2 = min(box1[2], box2[2])
    inter_y2 = min(box1[3], box2[3])

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    # Compute union
    box1_area = w1 * h1
    box2_area = w2 * h2
    union_area = box1_area + box2_area - inter_area

    if union_area == 0:
        return 0.0

    return inter_area / union_area


class TrackingEngine:
    """
    Multi-object tracking engine using IoU-based matching.

    Simplified implementation suitable for real-time person tracking.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize tracking engine.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        tracking_config = self.config.get('tracking', {})

        # Tracking parameters
        self.max_age = tracking_config.get('max_age', 30)
        self.min_hits = tracking_config.get('min_hits', 3)
        self.iou_threshold = tracking_config.get('iou_threshold', 0.3)

        # State
        self.tracks: Dict[int, Track] = {}
        self.next_track_id = 1
        self.frame_count = 0

        # Statistics
        self.total_tracks = 0
        self.active_tracks = 0

        logger.info("Tracking Engine initialized")

    def update(self, detections: List[Detection]) -> List[Track]:
        """
        Update tracks with new detections.

        Args:
            detections: List of detections from current frame

        Returns:
            List of active tracks
        """
        self.frame_count += 1

        # Predict all tracks
        for track in self.tracks.values():
            track.predict()

        # Match detections to tracks
        matched_indices = self._match_detections_to_tracks(detections)

        # Update matched tracks
        matched_track_ids = set()
        matched_detection_ids = set()

        for det_idx, track_id in matched_indices:
            detection = detections[det_idx]
            track = self.tracks[track_id]
            track.update(detection)
            matched_track_ids.add(track_id)
            matched_detection_ids.add(det_idx)

        # Create new tracks for unmatched detections
        for det_idx, detection in enumerate(detections):
            if det_idx not in matched_detection_ids:
                self._create_track(detection)

        # Remove old tracks
        self._remove_old_tracks()

        # Get active confirmed tracks
        active_tracks = [
            track for track in self.tracks.values()
            if track.state == "confirmed"
        ]

        self.active_tracks = len(active_tracks)

        return active_tracks

    def _match_detections_to_tracks(
        self,
        detections: List[Detection]
    ) -> List[Tuple[int, int]]:
        """
        Match detections to existing tracks using IoU.

        Args:
            detections: List of detections

        Returns:
            List of (detection_index, track_id) tuples
        """
        if not detections or not self.tracks:
            return []

        # Compute IoU matrix
        iou_matrix = np.zeros((len(detections), len(self.tracks)))

        track_ids = list(self.tracks.keys())
        for det_idx, detection in enumerate(detections):
            for track_idx, track_id in enumerate(track_ids):
                track = self.tracks[track_id]
                iou = compute_iou(detection.bbox, track.bbox)
                iou_matrix[det_idx, track_idx] = iou

        # Simple greedy matching
        matches = []
        matched_detections = set()
        matched_tracks = set()

        # Sort by IoU (highest first)
        while True:
            # Find maximum IoU
            max_iou = iou_matrix.max()

            if max_iou < self.iou_threshold:
                break

            # Get indices of maximum
            det_idx, track_idx = np.unravel_index(iou_matrix.argmax(), iou_matrix.shape)

            # Add match
            track_id = track_ids[track_idx]
            matches.append((det_idx, track_id))

            matched_detections.add(det_idx)
            matched_tracks.add(track_idx)

            # Zero out matched row and column
            iou_matrix[det_idx, :] = 0
            iou_matrix[:, track_idx] = 0

        return matches

    def _create_track(self, detection: Detection) -> Track:
        """
        Create a new track from detection.

        Args:
            detection: Detection to create track from

        Returns:
            Created track
        """
        track = Track(
            track_id=self.next_track_id,
            bbox=detection.bbox,
            confidence=detection.confidence,
            class_id=detection.class_id,
            class_name=detection.class_name,
            hits=1
        )

        self.tracks[self.next_track_id] = track
        self.next_track_id += 1
        self.total_tracks += 1

        return track

    def _remove_old_tracks(self):
        """Remove tracks that haven't been updated for too long."""
        tracks_to_remove = []

        for track_id, track in self.tracks.items():
            if track.time_since_update > self.max_age:
                tracks_to_remove.append(track_id)

        for track_id in tracks_to_remove:
            del self.tracks[track_id]

    def get_track(self, track_id: int) -> Optional[Track]:
        """
        Get track by ID.

        Args:
            track_id: Track ID

        Returns:
            Track object or None
        """
        return self.tracks.get(track_id)

    def get_all_tracks(self) -> List[Track]:
        """
        Get all active tracks.

        Returns:
            List of all tracks
        """
        return list(self.tracks.values())

    def get_confirmed_tracks(self) -> List[Track]:
        """
        Get only confirmed tracks.

        Returns:
            List of confirmed tracks
        """
        return [track for track in self.tracks.values() if track.state == "confirmed"]

    def get_statistics(self) -> Dict:
        """
        Get tracking statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            'total_tracks': self.total_tracks,
            'active_tracks': self.active_tracks,
            'current_tracks': len(self.tracks),
            'frame_count': self.frame_count,
            'max_age': self.max_age,
            'min_hits': self.min_hits,
            'iou_threshold': self.iou_threshold
        }

    def reset(self):
        """Reset tracking engine."""
        self.tracks.clear()
        self.next_track_id = 1
        self.frame_count = 0
        self.total_tracks = 0
        self.active_tracks = 0
        logger.info("Tracking engine reset")


if __name__ == "__main__":
    # Test tracking engine
    config = {
        'tracking': {
            'max_age': 30,
            'min_hits': 3,
            'iou_threshold': 0.3
        }
    }

    tracker = TrackingEngine(config)

    # Simulate detections
    det1 = Detection(bbox=(100, 100, 50, 100), confidence=0.9, class_id=0, class_name="person")
    det2 = Detection(bbox=(200, 150, 50, 100), confidence=0.85, class_id=0, class_name="person")

    # Frame 1
    tracks = tracker.update([det1, det2])
    print(f"Frame 1: {len(tracks)} tracks")

    # Frame 2 (slightly moved)
    det1_moved = Detection(bbox=(105, 105, 50, 100), confidence=0.9, class_id=0, class_name="person")
    det2_moved = Detection(bbox=(205, 155, 50, 100), confidence=0.85, class_id=0, class_name="person")

    tracks = tracker.update([det1_moved, det2_moved])
    print(f"Frame 2: {len(tracks)} tracks")

    # Statistics
    stats = tracker.get_statistics()
    print(f"Statistics: {stats}")
