#!/usr/bin/env python3
"""
Multi-Camera Intrusion Detection System
Main Application Entry Point

A production-grade, enterprise-level security monitoring application
with AI-powered behavioral analysis and threat assessment.
"""

import sys
import cv2
import time
import signal
from pathlib import Path
from typing import Optional

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.config_loader import ConfigLoader, get_config
from app.utils.logger import setup_main_logger, get_logger
from app.database.database_manager import DatabaseManager
from app.core.camera_manager import CameraManager
from app.core.detection_engine import DetectionEngine
from app.core.tracking_engine import TrackingEngine

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger = get_logger(__name__)
    logger.info("Shutdown signal received")
    shutdown_requested = True


class IntrusionDetectionSystem:
    """
    Main application class coordinating all components.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the intrusion detection system.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = ConfigLoader(config_path)
        config_dict = self.config.get_all()

        # Setup logging
        self.logger = setup_main_logger(config_dict)
        self.logger.info("Initializing Multi-Camera Intrusion Detection System...")

        # Initialize components
        self.database = None
        self.camera_manager = None
        self.detection_engine = None
        self.tracking_engines = {}  # One tracker per camera

        self.is_running = False

    def initialize(self) -> bool:
        """
        Initialize all system components.

        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("Initializing system components...")

            # Initialize database
            self.logger.info("Initializing database...")
            self.database = DatabaseManager(self.config.get_all())
            self.database.initialize()

            # Initialize camera manager
            self.logger.info("Initializing camera manager...")
            self.camera_manager = CameraManager(self.config.get_all())

            # Auto-detect cameras
            available_cameras = self.camera_manager.auto_detect_cameras(max_cameras=10)
            self.logger.info(f"Found {len(available_cameras)} camera(s)")

            if not available_cameras:
                self.logger.warning("No cameras detected!")
                return False

            # Initialize cameras
            if not self.camera_manager.initialize_cameras():
                self.logger.error("Failed to initialize cameras")
                return False

            # Initialize detection engine
            self.logger.info("Initializing detection engine...")
            self.detection_engine = DetectionEngine(self.config.get_all())

            if not self.detection_engine.initialize():
                self.logger.error("Failed to initialize detection engine")
                return False

            # Initialize tracking engines (one per camera)
            self.logger.info("Initializing tracking engines...")
            for camera_id in self.camera_manager.get_all_cameras().keys():
                tracker = TrackingEngine(self.config.get_all())
                self.tracking_engines[camera_id] = tracker

            # Start health monitoring
            self.camera_manager.start_health_monitor(interval=5.0)

            self.logger.info("All components initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    def run(self):
        """
        Main application loop.
        """
        global shutdown_requested

        if not self.is_running:
            self.logger.error("System not running. Call start() first.")
            return

        self.logger.info("Starting main processing loop...")

        try:
            frame_count = 0
            last_stats_time = time.time()

            while not shutdown_requested and self.is_running:
                # Get frames from all cameras
                frames = self.camera_manager.get_all_frames(latest=True)

                if not frames:
                    time.sleep(0.01)
                    continue

                # Process each camera's frame
                for camera_id, (frame, timestamp) in frames.items():
                    # Run detection
                    detections = self.detection_engine.detect(frame)

                    # Update tracker
                    tracker = self.tracking_engines.get(camera_id)
                    if tracker:
                        tracks = tracker.update(detections)

                        # Draw detections and tracks
                        output_frame = frame.copy()
                        output_frame = self.detection_engine.draw_detections(
                            output_frame,
                            detections,
                            show_confidence=True
                        )

                        # Draw tracks
                        for track in tracks:
                            x, y, w, h = track.bbox
                            # Draw track ID
                            cv2.putText(
                                output_frame,
                                f"ID:{track.track_id}",
                                (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                (0, 255, 255),
                                2
                            )

                            # Draw trajectory
                            if len(track.trajectory) > 1:
                                points = list(track.trajectory)
                                for i in range(len(points) - 1):
                                    cv2.line(
                                        output_frame,
                                        points[i],
                                        points[i + 1],
                                        (255, 0, 255),
                                        2
                                    )

                        # Display frame
                        camera = self.camera_manager.get_camera(camera_id)
                        window_name = f"{camera.name} - ID {camera_id}"
                        cv2.imshow(window_name, output_frame)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.logger.info("Quit requested by user")
                    break
                elif key == ord('s'):
                    # Print statistics
                    self._print_statistics()

                frame_count += 1

                # Print statistics every 10 seconds
                if time.time() - last_stats_time >= 10.0:
                    self._print_statistics()
                    last_stats_time = time.time()

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.logger.info("Main loop ended")

    def _print_statistics(self):
        """Print system statistics."""
        self.logger.info("=" * 60)
        self.logger.info("SYSTEM STATISTICS")
        self.logger.info("=" * 60)

        # Camera statistics
        cam_stats = self.camera_manager.get_statistics()
        for cam_id, stats in cam_stats.items():
            self.logger.info(f"Camera {cam_id} ({stats['name']}): "
                           f"{stats['fps']:.1f} FPS, "
                           f"{stats['dropped_frames']} dropped frames")

        # Detection statistics
        det_stats = self.detection_engine.get_statistics()
        self.logger.info(f"Detection: {det_stats['total_detections']} detections, "
                        f"{det_stats['inference_fps']:.1f} FPS, "
                        f"{det_stats['avg_inference_time']*1000:.1f}ms avg")

        # Tracking statistics
        for cam_id, tracker in self.tracking_engines.items():
            track_stats = tracker.get_statistics()
            self.logger.info(f"Tracking (Camera {cam_id}): "
                           f"{track_stats['total_tracks']} total tracks, "
                           f"{track_stats['active_tracks']} active")

        self.logger.info("=" * 60)

    def start(self) -> bool:
        """
        Start the system.

        Returns:
            True if started successfully
        """
        if self.is_running:
            self.logger.warning("System already running")
            return True

        if not self.initialize():
            self.logger.error("Failed to initialize system")
            return False

        self.is_running = True
        self.logger.info("System started successfully")
        return True

    def stop(self):
        """Stop the system and cleanup."""
        if not self.is_running:
            return

        self.logger.info("Stopping system...")

        self.is_running = False

        # Stop cameras
        if self.camera_manager:
            self.camera_manager.stop_all()

        # Close database
        if self.database:
            self.database.close()

        # Close all windows
        cv2.destroyAllWindows()

        self.logger.info("System stopped")


def main():
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(
        description="Multi-Camera Intrusion Detection System"
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to configuration file'
    )
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Launch GUI interface (default: basic OpenCV display)'
    )

    args = parser.parse_args()

    # Create and start system
    system = IntrusionDetectionSystem(config_path=args.config)

    try:
        if system.start():
            system.run()
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        system.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
