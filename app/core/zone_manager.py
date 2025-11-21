"""
Zone Manager
Manage security zones, geofencing, and zone violations.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
from datetime import datetime, time as dt_time
from shapely.geometry import Point, Polygon

from app.database.models import Zone, ZoneType
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityZone:
    """
    Represents a monitored security zone.
    """

    def __init__(
        self,
        zone_id: int,
        camera_id: int,
        name: str,
        zone_type: ZoneType,
        coordinates: List[Tuple[int, int]],
        rules: Optional[Dict] = None,
        color: str = "#FF0000"
    ):
        """
        Initialize security zone.

        Args:
            zone_id: Zone ID
            camera_id: Camera ID this zone belongs to
            name: Zone name
            zone_type: Type of zone
            coordinates: List of (x, y) polygon points
            rules: Zone-specific rules
            color: Display color (hex)
        """
        self.zone_id = zone_id
        self.camera_id = camera_id
        self.name = name
        self.zone_type = zone_type
        self.coordinates = coordinates
        self.rules = rules or {}
        self.color = color

        # Create Shapely polygon for point-in-polygon checks
        self.polygon = Polygon(coordinates)

        # Statistics
        self.current_occupancy = 0
        self.total_entries = 0
        self.total_exits = 0

        # Time-based activation
        self.time_based = self.rules.get('time_based', False)
        self.active_hours = self.rules.get('active_hours', ('00:00', '23:59'))

        logger.debug(f"Zone created: {name} ({zone_type.value})")

    def contains_point(self, x: int, y: int) -> bool:
        """
        Check if point is inside zone.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if point is in zone
        """
        point = Point(x, y)
        return self.polygon.contains(point)

    def contains_bbox(self, bbox: Tuple[int, int, int, int]) -> bool:
        """
        Check if bounding box intersects with zone.

        Args:
            bbox: Bounding box (x, y, w, h)

        Returns:
            True if bbox intersects zone
        """
        x, y, w, h = bbox

        # Check center point
        center_x = x + w // 2
        center_y = y + h // 2

        return self.contains_point(center_x, center_y)

    def is_active_now(self) -> bool:
        """
        Check if zone is currently active (time-based).

        Returns:
            True if zone is active
        """
        if not self.time_based:
            return True

        current_time = datetime.now().time()
        start_str, end_str = self.active_hours

        try:
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()

            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                # Overnight range
                return current_time >= start_time or current_time <= end_time

        except:
            return True

    def draw(self, frame: np.ndarray, thickness: int = 2) -> np.ndarray:
        """
        Draw zone on frame.

        Args:
            frame: Frame to draw on
            thickness: Line thickness

        Returns:
            Frame with zone drawn
        """
        # Convert hex color to BGR
        color_hex = self.color.lstrip('#')
        r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        bgr_color = (b, g, r)

        # Draw polygon
        pts = np.array(self.coordinates, np.int32)
        pts = pts.reshape((-1, 1, 2))

        # Draw filled polygon (semi-transparent)
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], bgr_color)
        frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

        # Draw border
        cv2.polylines(frame, [pts], True, bgr_color, thickness)

        # Draw label
        if len(self.coordinates) > 0:
            label_x, label_y = self.coordinates[0]
            cv2.putText(
                frame,
                self.name,
                (label_x, label_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                bgr_color,
                2
            )

        return frame


class ZoneManager:
    """
    Manages security zones across all cameras.

    Features:
    - Create/update/delete zones
    - Check zone violations
    - Track occupancy
    - Entry/exit counting
    - Time-based zone activation
    """

    def __init__(self, database=None):
        """
        Initialize zone manager.

        Args:
            database: DatabaseManager instance
        """
        self.database = database
        self.zones: Dict[int, Dict[int, SecurityZone]] = {}  # camera_id -> {zone_id -> zone}

        # Load zones from database
        self._load_zones()

        logger.info("Zone Manager initialized")

    def _load_zones(self):
        """Load zones from database."""
        if not self.database:
            return

        try:
            with self.database.session_scope() as session:
                db_zones = session.query(Zone).filter(Zone.active == True).all()

                for db_zone in db_zones:
                    # Parse coordinates
                    coords = db_zone.coordinates

                    # Create zone
                    zone = SecurityZone(
                        zone_id=db_zone.id,
                        camera_id=db_zone.camera_id,
                        name=db_zone.name,
                        zone_type=db_zone.zone_type,
                        coordinates=coords,
                        rules=db_zone.rules or {},
                        color=db_zone.color
                    )

                    # Add to camera zones
                    if db_zone.camera_id not in self.zones:
                        self.zones[db_zone.camera_id] = {}

                    self.zones[db_zone.camera_id][db_zone.id] = zone

                logger.info(f"Loaded {len(db_zones)} zones from database")

        except Exception as e:
            logger.error(f"Error loading zones: {e}")

    def add_zone(
        self,
        camera_id: int,
        name: str,
        zone_type: ZoneType,
        coordinates: List[Tuple[int, int]],
        rules: Optional[Dict] = None,
        color: str = "#FF0000"
    ) -> Optional[SecurityZone]:
        """
        Add new zone.

        Args:
            camera_id: Camera ID
            name: Zone name
            zone_type: Type of zone
            coordinates: Polygon coordinates
            rules: Zone rules
            color: Display color

        Returns:
            Created SecurityZone or None
        """
        try:
            # Save to database
            if self.database:
                db_zone = Zone(
                    camera_id=camera_id,
                    name=name,
                    zone_type=zone_type,
                    coordinates=coordinates,
                    rules=rules or {},
                    color=color,
                    active=True
                )

                self.database.add(db_zone)

                # Create SecurityZone
                zone = SecurityZone(
                    zone_id=db_zone.id,
                    camera_id=camera_id,
                    name=name,
                    zone_type=zone_type,
                    coordinates=coordinates,
                    rules=rules,
                    color=color
                )

                # Add to zones
                if camera_id not in self.zones:
                    self.zones[camera_id] = {}

                self.zones[camera_id][db_zone.id] = zone

                logger.info(f"Zone added: {name} (camera {camera_id})")
                return zone

        except Exception as e:
            logger.error(f"Error adding zone: {e}")

        return None

    def get_zones_for_camera(self, camera_id: int) -> List[SecurityZone]:
        """
        Get all zones for a camera.

        Args:
            camera_id: Camera ID

        Returns:
            List of zones
        """
        return list(self.zones.get(camera_id, {}).values())

    def check_zone_violations(
        self,
        camera_id: int,
        bbox: Tuple[int, int, int, int],
        track_id: int
    ) -> List[SecurityZone]:
        """
        Check if bounding box violates any zones.

        Args:
            camera_id: Camera ID
            bbox: Bounding box (x, y, w, h)
            track_id: Track ID

        Returns:
            List of violated zones
        """
        violations = []

        camera_zones = self.zones.get(camera_id, {})

        for zone in camera_zones.values():
            # Check if zone is active
            if not zone.is_active_now():
                continue

            # Check if bbox is in zone
            if zone.contains_bbox(bbox):
                # Restricted zones are always violations
                if zone.zone_type == ZoneType.RESTRICTED:
                    violations.append(zone)
                    logger.warning(f"Zone violation: Track {track_id} in restricted zone '{zone.name}'")

                # Update occupancy
                zone.current_occupancy += 1

        return violations

    def check_entry_exit(
        self,
        camera_id: int,
        prev_bbox: Tuple[int, int, int, int],
        curr_bbox: Tuple[int, int, int, int],
        track_id: int
    ) -> Dict[str, List[SecurityZone]]:
        """
        Check for zone entries and exits.

        Args:
            camera_id: Camera ID
            prev_bbox: Previous bounding box
            curr_bbox: Current bounding box
            track_id: Track ID

        Returns:
            Dictionary with 'entered' and 'exited' zone lists
        """
        result = {'entered': [], 'exited': []}

        camera_zones = self.zones.get(camera_id, {})

        for zone in camera_zones.values():
            # Check previous and current positions
            was_in_zone = zone.contains_bbox(prev_bbox)
            is_in_zone = zone.contains_bbox(curr_bbox)

            # Entry
            if not was_in_zone and is_in_zone:
                result['entered'].append(zone)
                zone.total_entries += 1
                logger.debug(f"Track {track_id} entered zone '{zone.name}'")

            # Exit
            elif was_in_zone and not is_in_zone:
                result['exited'].append(zone)
                zone.total_exits += 1
                logger.debug(f"Track {track_id} exited zone '{zone.name}'")

        return result

    def draw_zones(self, camera_id: int, frame: np.ndarray) -> np.ndarray:
        """
        Draw all zones for a camera on frame.

        Args:
            camera_id: Camera ID
            frame: Frame to draw on

        Returns:
            Frame with zones drawn
        """
        camera_zones = self.zones.get(camera_id, {})

        for zone in camera_zones.values():
            if zone.is_active_now():
                frame = zone.draw(frame)

        return frame

    def get_zone_statistics(self, camera_id: int) -> Dict:
        """
        Get statistics for all zones on a camera.

        Args:
            camera_id: Camera ID

        Returns:
            Dictionary of zone statistics
        """
        stats = {}

        camera_zones = self.zones.get(camera_id, {})

        for zone_id, zone in camera_zones.items():
            stats[zone_id] = {
                'name': zone.name,
                'type': zone.zone_type.value,
                'occupancy': zone.current_occupancy,
                'total_entries': zone.total_entries,
                'total_exits': zone.total_exits,
                'is_active': zone.is_active_now()
            }

        return stats


if __name__ == "__main__":
    # Test zone manager
    zone_manager = ZoneManager()

    # Add test zone (rectangular area)
    zone = zone_manager.add_zone(
        camera_id=0,
        name="Restricted Area",
        zone_type=ZoneType.RESTRICTED,
        coordinates=[(100, 100), (300, 100), (300, 300), (100, 300)],
        color="#FF0000"
    )

    # Test point containment
    print(f"Point (200, 200) in zone: {zone.contains_point(200, 200)}")
    print(f"Point (50, 50) in zone: {zone.contains_point(50, 50)}")

    # Test bbox containment
    print(f"BBox (150, 150, 50, 50) in zone: {zone.contains_bbox((150, 150, 50, 50))}")
    print(f"BBox (50, 50, 30, 30) in zone: {zone.contains_bbox((50, 50, 30, 30))}")

    # Check violation
    violations = zone_manager.check_zone_violations(0, (200, 200, 50, 50), track_id=1)
    print(f"Violations: {len(violations)}")

    print("Test complete")
