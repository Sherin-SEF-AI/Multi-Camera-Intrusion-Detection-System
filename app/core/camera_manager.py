"""
Camera Manager
Manages multiple USB webcams with auto-detection, health monitoring, and configuration.
"""

import cv2
import time
import threading
from queue import Queue, Empty
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import numpy as np

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CameraInfo:
    """Information about a camera."""
    id: int
    name: str
    resolution: Tuple[int, int]  # (width, height)
    fps: int
    enabled: bool
    is_connected: bool = False
    current_fps: float = 0.0
    dropped_frames: int = 0
    last_frame_time: float = 0.0


class Camera:
    """
    Represents a single camera with its capture device and settings.
    """

    def __init__(
        self,
        camera_id: int,
        name: str = "",
        resolution: Tuple[int, int] = (1280, 720),
        fps: int = 30,
        buffer_size: int = 100
    ):
        """
        Initialize camera.

        Args:
            camera_id: Camera device ID
            name: Human-readable camera name
            resolution: Desired resolution (width, height)
            fps: Desired frames per second
            buffer_size: Maximum number of frames to buffer
        """
        self.camera_id = camera_id
        self.name = name or f"Camera {camera_id}"
        self.resolution = resolution
        self.target_fps = fps
        self.buffer_size = buffer_size

        self.capture: Optional[cv2.VideoCapture] = None
        self.is_connected = False
        self.is_running = False

        # Frame buffer
        self.frame_queue: Queue = Queue(maxsize=buffer_size)

        # Statistics
        self.frame_count = 0
        self.dropped_frames = 0
        self.current_fps = 0.0
        self.last_frame_time = 0.0
        self.fps_update_time = time.time()
        self.fps_frame_count = 0

        # Threading
        self.capture_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        logger.info(f"Camera initialized: {self.name} (ID: {camera_id})")

    def connect(self) -> bool:
        """
        Connect to camera device.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to open camera
            self.capture = cv2.VideoCapture(self.camera_id)

            if not self.capture.isOpened():
                logger.error(f"Failed to open camera {self.camera_id}")
                return False

            # Set camera properties
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.capture.set(cv2.CAP_PROP_FPS, self.target_fps)

            # Verify actual resolution
            actual_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.capture.get(cv2.CAP_PROP_FPS))

            logger.info(
                f"{self.name}: Connected successfully "
                f"[{actual_width}x{actual_height}@{actual_fps}fps]"
            )

            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"Error connecting to camera {self.camera_id}: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from camera device."""
        if self.capture is not None:
            self.capture.release()
            self.capture = None

        self.is_connected = False
        logger.info(f"{self.name}: Disconnected")

    def start_capture(self) -> bool:
        """
        Start capturing frames in a separate thread.

        Returns:
            True if capture started successfully, False otherwise
        """
        if not self.is_connected:
            logger.error(f"{self.name}: Cannot start capture - not connected")
            return False

        if self.is_running:
            logger.warning(f"{self.name}: Already capturing")
            return True

        # Reset stop event
        self.stop_event.clear()

        # Start capture thread
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            name=f"Camera{self.camera_id}Thread",
            daemon=True
        )
        self.capture_thread.start()

        self.is_running = True
        logger.info(f"{self.name}: Started capturing")
        return True

    def stop_capture(self) -> None:
        """Stop capturing frames."""
        if not self.is_running:
            return

        # Signal stop
        self.stop_event.set()

        # Wait for thread to finish
        if self.capture_thread is not None:
            self.capture_thread.join(timeout=2.0)

        self.is_running = False
        logger.info(f"{self.name}: Stopped capturing")

    def _capture_loop(self) -> None:
        """Internal capture loop running in separate thread."""
        logger.info(f"{self.name}: Capture loop started")

        while not self.stop_event.is_set():
            try:
                # Capture frame
                ret, frame = self.capture.read()

                if not ret:
                    logger.warning(f"{self.name}: Failed to read frame")
                    time.sleep(0.1)
                    continue

                # Update statistics
                current_time = time.time()
                self.frame_count += 1
                self.fps_frame_count += 1
                self.last_frame_time = current_time

                # Calculate FPS every second
                if current_time - self.fps_update_time >= 1.0:
                    self.current_fps = self.fps_frame_count / (current_time - self.fps_update_time)
                    self.fps_frame_count = 0
                    self.fps_update_time = current_time

                # Add frame to queue (non-blocking)
                try:
                    self.frame_queue.put_nowait((frame, current_time))
                except:
                    # Queue full - drop frame
                    self.dropped_frames += 1

                # Control frame rate
                time.sleep(1.0 / self.target_fps)

            except Exception as e:
                logger.error(f"{self.name}: Error in capture loop: {e}")
                time.sleep(0.1)

        logger.info(f"{self.name}: Capture loop ended")

    def get_frame(self, timeout: float = 1.0) -> Optional[Tuple[np.ndarray, float]]:
        """
        Get the latest frame from the buffer.

        Args:
            timeout: Maximum time to wait for frame (seconds)

        Returns:
            Tuple of (frame, timestamp) or None if no frame available
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except Empty:
            return None

    def get_latest_frame(self) -> Optional[Tuple[np.ndarray, float]]:
        """
        Get the most recent frame, discarding older frames.

        Returns:
            Tuple of (frame, timestamp) or None if no frame available
        """
        frame = None
        try:
            # Get all frames from queue, keeping only the latest
            while True:
                frame = self.frame_queue.get_nowait()
        except Empty:
            pass

        return frame

    def set_property(self, prop: int, value: Any) -> bool:
        """
        Set camera property.

        Args:
            prop: OpenCV property ID (cv2.CAP_PROP_*)
            value: Property value

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected or self.capture is None:
            return False

        try:
            return self.capture.set(prop, value)
        except Exception as e:
            logger.error(f"{self.name}: Error setting property: {e}")
            return False

    def get_property(self, prop: int) -> Optional[float]:
        """
        Get camera property.

        Args:
            prop: OpenCV property ID (cv2.CAP_PROP_*)

        Returns:
            Property value or None if error
        """
        if not self.is_connected or self.capture is None:
            return None

        try:
            return self.capture.get(prop)
        except Exception as e:
            logger.error(f"{self.name}: Error getting property: {e}")
            return None

    def get_info(self) -> CameraInfo:
        """
        Get camera information and statistics.

        Returns:
            CameraInfo object
        """
        return CameraInfo(
            id=self.camera_id,
            name=self.name,
            resolution=self.resolution,
            fps=self.target_fps,
            enabled=self.is_running,
            is_connected=self.is_connected,
            current_fps=self.current_fps,
            dropped_frames=self.dropped_frames,
            last_frame_time=self.last_frame_time
        )


class CameraManager:
    """
    Manages multiple cameras with auto-detection and health monitoring.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize camera manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.cameras: Dict[int, Camera] = {}
        self.health_monitor_thread: Optional[threading.Thread] = None
        self.stop_health_monitor = threading.Event()

        logger.info("Camera Manager initialized")

    def auto_detect_cameras(self, max_cameras: int = 10) -> List[int]:
        """
        Auto-detect available cameras.

        Args:
            max_cameras: Maximum number of cameras to check

        Returns:
            List of available camera IDs
        """
        logger.info(f"Auto-detecting cameras (checking 0-{max_cameras-1})...")
        available_cameras = []

        for camera_id in range(max_cameras):
            try:
                cap = cv2.VideoCapture(camera_id)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        available_cameras.append(camera_id)
                        logger.info(f"Detected camera at ID {camera_id}")
                cap.release()
            except Exception as e:
                logger.debug(f"Error checking camera {camera_id}: {e}")

        logger.info(f"Found {len(available_cameras)} camera(s): {available_cameras}")
        return available_cameras

    def initialize_cameras(self, camera_configs: Optional[List[dict]] = None) -> bool:
        """
        Initialize cameras based on configuration.

        Args:
            camera_configs: List of camera configuration dictionaries

        Returns:
            True if at least one camera initialized successfully
        """
        # Get configuration
        if camera_configs is None:
            cam_config = self.config.get('cameras', {})
            camera_configs = cam_config.get('camera_configs', [])

        if not camera_configs:
            logger.warning("No camera configurations provided")
            return False

        success_count = 0

        for config in camera_configs:
            camera_id = config.get('id', 0)
            name = config.get('name', f"Camera {camera_id}")
            resolution = tuple(config.get('resolution', [1280, 720]))
            fps = config.get('fps', 30)
            enabled = config.get('enabled', True)

            if not enabled:
                logger.info(f"Camera {camera_id} is disabled, skipping")
                continue

            # Create camera
            camera = Camera(
                camera_id=camera_id,
                name=name,
                resolution=resolution,
                fps=fps
            )

            # Connect and start capture
            if camera.connect():
                if camera.start_capture():
                    self.cameras[camera_id] = camera
                    success_count += 1
                else:
                    camera.disconnect()

        logger.info(f"Initialized {success_count}/{len(camera_configs)} cameras")
        return success_count > 0

    def get_camera(self, camera_id: int) -> Optional[Camera]:
        """
        Get camera by ID.

        Args:
            camera_id: Camera ID

        Returns:
            Camera object or None if not found
        """
        return self.cameras.get(camera_id)

    def get_all_cameras(self) -> Dict[int, Camera]:
        """
        Get all cameras.

        Returns:
            Dictionary of camera_id -> Camera
        """
        return self.cameras.copy()

    def get_frame(self, camera_id: int, latest: bool = False) -> Optional[Tuple[np.ndarray, float]]:
        """
        Get frame from specific camera.

        Args:
            camera_id: Camera ID
            latest: If True, get most recent frame (discard buffer)

        Returns:
            Tuple of (frame, timestamp) or None
        """
        camera = self.cameras.get(camera_id)
        if camera is None:
            return None

        if latest:
            return camera.get_latest_frame()
        else:
            return camera.get_frame()

    def get_all_frames(self, latest: bool = True) -> Dict[int, Tuple[np.ndarray, float]]:
        """
        Get frames from all cameras.

        Args:
            latest: If True, get most recent frames

        Returns:
            Dictionary of camera_id -> (frame, timestamp)
        """
        frames = {}
        for camera_id, camera in self.cameras.items():
            if latest:
                frame_data = camera.get_latest_frame()
            else:
                frame_data = camera.get_frame(timeout=0.1)

            if frame_data is not None:
                frames[camera_id] = frame_data

        return frames

    def start_health_monitor(self, interval: float = 5.0) -> None:
        """
        Start health monitoring thread.

        Args:
            interval: Monitoring interval in seconds
        """
        if self.health_monitor_thread is not None:
            logger.warning("Health monitor already running")
            return

        self.stop_health_monitor.clear()
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            args=(interval,),
            name="HealthMonitor",
            daemon=True
        )
        self.health_monitor_thread.start()
        logger.info("Health monitor started")

    def _health_monitor_loop(self, interval: float) -> None:
        """Health monitoring loop."""
        while not self.stop_health_monitor.is_set():
            try:
                # Check each camera
                for camera_id, camera in self.cameras.items():
                    info = camera.get_info()

                    # Check for issues
                    if not info.is_connected:
                        logger.warning(f"{camera.name}: Disconnected!")
                        # TODO: Attempt reconnection

                    if info.current_fps < info.fps * 0.5:
                        logger.warning(
                            f"{camera.name}: Low FPS ({info.current_fps:.1f}/{info.fps})"
                        )

                    if info.dropped_frames > 100:
                        logger.warning(
                            f"{camera.name}: High dropped frames ({info.dropped_frames})"
                        )

                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                time.sleep(interval)

    def stop_all(self) -> None:
        """Stop all cameras and cleanup."""
        logger.info("Stopping all cameras...")

        # Stop health monitor
        if self.health_monitor_thread is not None:
            self.stop_health_monitor.set()
            self.health_monitor_thread.join(timeout=2.0)

        # Stop all cameras
        for camera in self.cameras.values():
            camera.stop_capture()
            camera.disconnect()

        self.cameras.clear()
        logger.info("All cameras stopped")

    def get_statistics(self) -> Dict[int, dict]:
        """
        Get statistics for all cameras.

        Returns:
            Dictionary of camera_id -> statistics
        """
        stats = {}
        for camera_id, camera in self.cameras.items():
            info = camera.get_info()
            stats[camera_id] = {
                'name': info.name,
                'connected': info.is_connected,
                'fps': info.current_fps,
                'target_fps': info.fps,
                'dropped_frames': info.dropped_frames,
                'resolution': info.resolution,
                'last_frame_time': info.last_frame_time
            }
        return stats


if __name__ == "__main__":
    # Test camera manager
    config = {
        'cameras': {
            'camera_configs': [
                {'id': 0, 'name': 'Test Camera', 'resolution': [640, 480], 'fps': 30, 'enabled': True}
            ]
        }
    }

    manager = CameraManager(config)

    # Auto-detect
    available = manager.auto_detect_cameras()
    print(f"Available cameras: {available}")

    # Initialize
    if manager.initialize_cameras():
        print("Cameras initialized")

        # Get some frames
        for i in range(10):
            frames = manager.get_all_frames()
            print(f"Frame {i}: Got {len(frames)} frames")
            time.sleep(0.1)

        # Get statistics
        stats = manager.get_statistics()
        for cam_id, stat in stats.items():
            print(f"Camera {cam_id}: {stat}")

    manager.stop_all()
    print("Test complete")
