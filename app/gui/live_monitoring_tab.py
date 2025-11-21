"""
Live Monitoring Tab
Real-time multi-camera view with detection and tracking visualization.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QGroupBox, QPushButton, QSlider, QComboBox, QListWidget,
    QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont
import cv2
import numpy as np
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)


class CameraWidget(QLabel):
    """
    Widget for displaying a single camera feed with detections.
    """

    def __init__(self, camera_id, camera_name):
        super().__init__()

        self.camera_id = camera_id
        self.camera_name = camera_name

        self.setMinimumSize(320, 240)
        self.setScaledContents(True)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #3d3d3d;
                background-color: #000000;
            }
        """)

        # Placeholder
        self._show_placeholder()

    def _show_placeholder(self):
        """Show placeholder when no frame is available."""
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            placeholder,
            f"{self.camera_name}",
            (50, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (100, 100, 100),
            2
        )
        cv2.putText(
            placeholder,
            "Waiting for camera...",
            (150, 280),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (80, 80, 80),
            1
        )
        self.update_frame(placeholder)

    def update_frame(self, frame_bgr):
        """
        Update the displayed frame.

        Args:
            frame_bgr: Frame in BGR format (OpenCV)
        """
        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            # Get dimensions
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w

            # Create QImage
            q_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            # Set pixmap
            pixmap = QPixmap.fromImage(q_image)
            self.setPixmap(pixmap)

        except Exception as e:
            logger.error(f"Error updating frame for camera {self.camera_id}: {e}")


class ThreatIndicator(QWidget):
    """
    Widget showing current threat level.
    """

    def __init__(self):
        super().__init__()

        self.threat_level = 0  # 0-100

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("THREAT LEVEL")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Level display
        self.level_label = QLabel("LOW")
        self.level_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.level_label)

        # Score
        self.score_label = QLabel("0")
        self.score_label.setFont(QFont("Segoe UI", 14))
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.score_label)

        self._update_display()

    def set_threat_level(self, level):
        """
        Set threat level (0-100).

        Args:
            level: Threat level score
        """
        self.threat_level = max(0, min(100, level))
        self._update_display()

    def _update_display(self):
        """Update visual display based on threat level."""
        level = self.threat_level

        if level < 25:
            level_text = "LOW"
            color = "#4caf50"  # Green
        elif level < 50:
            level_text = "MEDIUM"
            color = "#ff9800"  # Orange
        elif level < 75:
            level_text = "HIGH"
            color = "#ff5722"  # Deep Orange
        else:
            level_text = "CRITICAL"
            color = "#f44336"  # Red

        self.level_label.setText(level_text)
        self.score_label.setText(str(int(level)))

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border-radius: 8px;
            }}
            QLabel {{
                color: white;
            }}
        """)


class LiveMonitoringTab(QWidget):
    """
    Live monitoring tab with multi-camera grid view.
    """

    def __init__(self, system):
        super().__init__()

        self.system = system
        self.camera_widgets = {}
        self.is_monitoring = False

        self._init_ui()

        # Start update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_frames)
        self.update_timer.start(33)  # ~30 FPS

    def _init_ui(self):
        """Initialize UI."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Left panel - Camera grid
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Camera grid
        camera_group = QGroupBox("Camera Feeds")
        camera_layout = QGridLayout(camera_group)

        # Create camera widgets (3 cameras + 1 merged view)
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        camera_names = ["Camera 1", "Camera 2", "Camera 3", "All Cameras"]

        for i, (name, pos) in enumerate(zip(camera_names, positions)):
            cam_widget = CameraWidget(i, name)
            self.camera_widgets[i] = cam_widget
            camera_layout.addWidget(cam_widget, pos[0], pos[1])

        left_layout.addWidget(camera_group)

        # Control panel
        control_panel = self._create_control_panel()
        left_layout.addWidget(control_panel)

        # Right panel - Information
        right_panel = self._create_right_panel()

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _create_control_panel(self):
        """Create control panel."""
        group = QGroupBox("Controls")
        layout = QHBoxLayout(group)

        # Confidence threshold
        layout.addWidget(QLabel("Confidence:"))
        self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.confidence_slider.setMinimum(10)
        self.confidence_slider.setMaximum(100)
        self.confidence_slider.setValue(50)
        self.confidence_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.confidence_slider.setTickInterval(10)
        layout.addWidget(self.confidence_slider)

        self.confidence_label = QLabel("0.50")
        self.confidence_slider.valueChanged.connect(
            lambda v: self.confidence_label.setText(f"{v/100:.2f}")
        )
        layout.addWidget(self.confidence_label)

        layout.addSpacing(20)

        # Grid layout selector
        layout.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["2x2 Grid", "1x3 Grid", "Single View"])
        layout.addWidget(self.layout_combo)

        layout.addSpacing(20)

        # Show options
        self.show_confidence_check = QPushButton("Show Confidence")
        self.show_confidence_check.setCheckable(True)
        self.show_confidence_check.setChecked(True)
        layout.addWidget(self.show_confidence_check)

        self.show_trajectory_check = QPushButton("Show Trajectories")
        self.show_trajectory_check.setCheckable(True)
        self.show_trajectory_check.setChecked(True)
        layout.addWidget(self.show_trajectory_check)

        layout.addStretch()

        return group

    def _create_right_panel(self):
        """Create right information panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Threat indicator
        self.threat_indicator = ThreatIndicator()
        layout.addWidget(self.threat_indicator)

        # Active threats
        threats_group = QGroupBox("Active Threats")
        threats_layout = QVBoxLayout(threats_group)

        self.threats_list = QListWidget()
        self.threats_list.setStyleSheet("""
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3d3d3d;
            }
        """)
        threats_layout.addWidget(self.threats_list)

        layout.addWidget(threats_group)

        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.stats_labels = {}
        stats_items = [
            ("Persons Detected", "persons"),
            ("Active Tracks", "tracks"),
            ("Zone Violations", "violations"),
            ("Alerts Today", "alerts")
        ]

        for label_text, key in stats_items:
            stat_widget = QWidget()
            stat_layout = QHBoxLayout(stat_widget)
            stat_layout.setContentsMargins(0, 0, 0, 0)

            stat_label = QLabel(f"{label_text}:")
            stat_layout.addWidget(stat_label)

            stat_value = QLabel("0")
            stat_value.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            stat_value.setStyleSheet("color: #0d47a1;")
            stat_layout.addWidget(stat_value)

            stat_layout.addStretch()

            stats_layout.addWidget(stat_widget)
            self.stats_labels[key] = stat_value

        layout.addWidget(stats_group)

        # Recent events
        events_group = QGroupBox("Recent Events")
        events_layout = QVBoxLayout(events_group)

        self.events_list = QListWidget()
        events_layout.addWidget(self.events_list)

        layout.addWidget(events_group)

        layout.addStretch()

        return panel

    def _update_frames(self):
        """Update camera frames."""
        if not self.system or not self.system.is_running:
            return

        try:
            # Get frames from camera manager
            if self.system.camera_manager:
                frames = self.system.camera_manager.get_all_frames(latest=True)

                for camera_id, (frame, timestamp) in frames.items():
                    if camera_id in self.camera_widgets:
                        # Run detection if available
                        if self.system.detection_engine:
                            detections = self.system.detection_engine.detect(frame)

                            # Get tracker for this camera
                            if camera_id in self.system.tracking_engines:
                                tracker = self.system.tracking_engines[camera_id]
                                tracks = tracker.update(detections)

                                # Draw detections and tracks
                                frame = self._draw_detections_and_tracks(
                                    frame, detections, tracks
                                )

                        # Update widget
                        if camera_id < 3:  # Only update first 3 cameras
                            self.camera_widgets[camera_id].update_frame(frame)

                # Update statistics
                self._update_statistics()

        except Exception as e:
            logger.error(f"Error updating frames: {e}")

    def _draw_detections_and_tracks(self, frame, detections, tracks):
        """
        Draw detections and tracks on frame.

        Args:
            frame: Input frame
            detections: List of detections
            tracks: List of tracks

        Returns:
            Annotated frame
        """
        output = frame.copy()

        show_confidence = self.show_confidence_check.isChecked()
        show_trajectory = self.show_trajectory_check.isChecked()

        # Draw tracks
        for track in tracks:
            x, y, w, h = track.bbox

            # Draw bounding box
            color = (0, 255, 0)  # Green for normal
            cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)

            # Draw track ID
            label = f"ID:{track.track_id}"
            if show_confidence:
                label += f" {track.confidence:.2f}"

            cv2.putText(
                output,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )

            # Draw trajectory
            if show_trajectory and len(track.trajectory) > 1:
                points = list(track.trajectory)
                for i in range(len(points) - 1):
                    cv2.line(output, points[i], points[i + 1], (255, 0, 255), 2)

        # Draw FPS
        if hasattr(self.system.detection_engine, 'get_statistics'):
            stats = self.system.detection_engine.get_statistics()
            fps = stats.get('inference_fps', 0)
            cv2.putText(
                output,
                f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        return output

    def _update_statistics(self):
        """Update statistics display."""
        try:
            # Count total tracks
            total_tracks = 0
            for tracker in self.system.tracking_engines.values():
                stats = tracker.get_statistics()
                total_tracks += stats.get('active_tracks', 0)

            self.stats_labels['tracks'].setText(str(total_tracks))

            # Update other stats (placeholder for now)
            # TODO: Get real stats from database
            self.stats_labels['persons'].setText(str(total_tracks))
            self.stats_labels['violations'].setText("0")
            self.stats_labels['alerts'].setText("0")

        except Exception as e:
            logger.error(f"Error updating statistics: {e}")

    def add_threat(self, threat_info):
        """Add threat to the list."""
        self.threats_list.addItem(threat_info)

    def add_event(self, event_info):
        """Add event to the list."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.events_list.insertItem(0, f"[{timestamp}] {event_info}")

        # Keep only last 20 events
        while self.events_list.count() > 20:
            self.events_list.takeItem(self.events_list.count() - 1)
