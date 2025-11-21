"""
Settings Tab
System configuration and settings management.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QFormLayout, QMessageBox, QScrollArea, QTabWidget
)
from PyQt6.QtCore import Qt

from app.utils.logger import get_logger

logger = get_logger(__name__)


class SettingsTab(QWidget):
    """
    System settings and configuration tab.
    """

    def __init__(self, system):
        super().__init__()

        self.system = system
        self.config = system.config

        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # Create settings categories
        self._create_camera_settings(content_layout)
        self._create_detection_settings(content_layout)
        self._create_tracking_settings(content_layout)
        self._create_alert_settings(content_layout)
        self._create_recording_settings(content_layout)

        content_layout.addStretch()

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # Bottom buttons
        button_layout = QHBoxLayout()

        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)

        reset_btn = QPushButton("🔄 Reset to Defaults")
        reset_btn.clicked.connect(self._reset_settings)
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

    def _create_camera_settings(self, parent_layout):
        """Create camera settings section."""
        group = QGroupBox("Camera Settings")
        layout = QFormLayout(group)

        # Default Resolution
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "640x480",
            "1280x720",
            "1920x1080"
        ])
        current_res = self.config.get('cameras.default_resolution', [1280, 720])
        self.resolution_combo.setCurrentText(f"{current_res[0]}x{current_res[1]}")
        layout.addRow("Default Resolution:", self.resolution_combo)

        # Default FPS
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 60)
        self.fps_spin.setValue(self.config.get('cameras.default_fps', 30))
        layout.addRow("Default FPS:", self.fps_spin)

        # Buffer Size
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(10, 500)
        self.buffer_spin.setValue(self.config.get('cameras.frame_buffer_size', 100))
        layout.addRow("Frame Buffer Size:", self.buffer_spin)

        parent_layout.addWidget(group)

    def _create_detection_settings(self, parent_layout):
        """Create detection settings section."""
        group = QGroupBox("Detection Settings")
        layout = QFormLayout(group)

        # Model
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "yolov8n.pt",
            "yolov8s.pt",
            "yolov8m.pt",
            "yolov8l.pt",
            "yolov8x.pt"
        ])
        self.model_combo.setCurrentText(self.config.get('detection.model', 'yolov8n.pt'))
        layout.addRow("YOLO Model:", self.model_combo)

        # Confidence Threshold
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(self.config.get('detection.confidence_threshold', 0.5))
        layout.addRow("Confidence Threshold:", self.confidence_spin)

        # IOU Threshold
        self.iou_spin = QDoubleSpinBox()
        self.iou_spin.setRange(0.1, 1.0)
        self.iou_spin.setSingleStep(0.05)
        self.iou_spin.setValue(self.config.get('detection.iou_threshold', 0.45))
        layout.addRow("IOU Threshold:", self.iou_spin)

        # Device
        self.device_combo = QComboBox()
        self.device_combo.addItems(["cuda", "cpu", "mps"])
        self.device_combo.setCurrentText(self.config.get('detection.device', 'cuda'))
        layout.addRow("Device:", self.device_combo)

        # Half Precision
        self.half_precision_check = QCheckBox("Enable FP16 (faster on GPU)")
        self.half_precision_check.setChecked(self.config.get('detection.half_precision', False))
        layout.addRow("Half Precision:", self.half_precision_check)

        parent_layout.addWidget(group)

    def _create_tracking_settings(self, parent_layout):
        """Create tracking settings section."""
        group = QGroupBox("Tracking Settings")
        layout = QFormLayout(group)

        # Max Age
        self.max_age_spin = QSpinBox()
        self.max_age_spin.setRange(5, 100)
        self.max_age_spin.setValue(self.config.get('tracking.max_age', 30))
        layout.addRow("Max Age (frames):", self.max_age_spin)

        # Min Hits
        self.min_hits_spin = QSpinBox()
        self.min_hits_spin.setRange(1, 20)
        self.min_hits_spin.setValue(self.config.get('tracking.min_hits', 3))
        layout.addRow("Min Hits:", self.min_hits_spin)

        # IOU Threshold
        self.track_iou_spin = QDoubleSpinBox()
        self.track_iou_spin.setRange(0.1, 1.0)
        self.track_iou_spin.setSingleStep(0.05)
        self.track_iou_spin.setValue(self.config.get('tracking.iou_threshold', 0.3))
        layout.addRow("IOU Threshold:", self.track_iou_spin)

        parent_layout.addWidget(group)

    def _create_alert_settings(self, parent_layout):
        """Create alert settings section."""
        group = QGroupBox("Alert Settings")
        layout = QFormLayout(group)

        # Enable Alerts
        self.alerts_enabled_check = QCheckBox("Enable Alerts")
        self.alerts_enabled_check.setChecked(self.config.get('alerts.enabled', True))
        layout.addRow("", self.alerts_enabled_check)

        # Email Settings
        email_label = QLabel("<b>Email Alerts</b>")
        layout.addRow("", email_label)

        self.email_enabled_check = QCheckBox("Enable Email Alerts")
        self.email_enabled_check.setChecked(self.config.get('alerts.email.enabled', True))
        layout.addRow("", self.email_enabled_check)

        self.smtp_server_edit = QLineEdit()
        self.smtp_server_edit.setText(self.config.get('alerts.email.smtp_server', 'smtp.gmail.com'))
        layout.addRow("SMTP Server:", self.smtp_server_edit)

        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(self.config.get('alerts.email.smtp_port', 587))
        layout.addRow("SMTP Port:", self.smtp_port_spin)

        self.sender_email_edit = QLineEdit()
        self.sender_email_edit.setText(self.config.get('alerts.email.sender_email', ''))
        layout.addRow("Sender Email:", self.sender_email_edit)

        # SMS Settings
        sms_label = QLabel("<b>SMS Alerts (Twilio)</b>")
        layout.addRow("", sms_label)

        self.sms_enabled_check = QCheckBox("Enable SMS Alerts")
        self.sms_enabled_check.setChecked(self.config.get('alerts.sms.enabled', False))
        layout.addRow("", self.sms_enabled_check)

        parent_layout.addWidget(group)

    def _create_recording_settings(self, parent_layout):
        """Create recording settings section."""
        group = QGroupBox("Recording Settings")
        layout = QFormLayout(group)

        # Enable Recording
        self.recording_enabled_check = QCheckBox("Enable Recording")
        self.recording_enabled_check.setChecked(self.config.get('recording.enabled', True))
        layout.addRow("", self.recording_enabled_check)

        # Mode
        self.recording_mode_combo = QComboBox()
        self.recording_mode_combo.addItems([
            "event_triggered",
            "continuous",
            "manual"
        ])
        self.recording_mode_combo.setCurrentText(self.config.get('recording.mode', 'event_triggered'))
        layout.addRow("Mode:", self.recording_mode_combo)

        # Codec
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["h264", "h265", "mjpeg"])
        self.codec_combo.setCurrentText(self.config.get('recording.codec', 'h264'))
        layout.addRow("Codec:", self.codec_combo)

        # Quality
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["low", "medium", "high"])
        self.quality_combo.setCurrentText(self.config.get('recording.quality', 'medium'))
        layout.addRow("Quality:", self.quality_combo)

        # Pre-event Duration
        self.pre_event_spin = QSpinBox()
        self.pre_event_spin.setRange(5, 60)
        self.pre_event_spin.setValue(self.config.get('recording.pre_event_duration', 10))
        layout.addRow("Pre-Event Duration (s):", self.pre_event_spin)

        # Post-event Duration
        self.post_event_spin = QSpinBox()
        self.post_event_spin.setRange(10, 120)
        self.post_event_spin.setValue(self.config.get('recording.post_event_duration', 30))
        layout.addRow("Post-Event Duration (s):", self.post_event_spin)

        # Storage Limit
        self.storage_spin = QSpinBox()
        self.storage_spin.setRange(10, 10000)
        self.storage_spin.setValue(self.config.get('recording.max_storage_gb', 500))
        layout.addRow("Max Storage (GB):", self.storage_spin)

        parent_layout.addWidget(group)

    def _save_settings(self):
        """Save settings to configuration."""
        try:
            # Camera settings
            res = self.resolution_combo.currentText().split('x')
            self.config.set('cameras.default_resolution', [int(res[0]), int(res[1])])
            self.config.set('cameras.default_fps', self.fps_spin.value())
            self.config.set('cameras.frame_buffer_size', self.buffer_spin.value())

            # Detection settings
            self.config.set('detection.model', self.model_combo.currentText())
            self.config.set('detection.confidence_threshold', self.confidence_spin.value())
            self.config.set('detection.iou_threshold', self.iou_spin.value())
            self.config.set('detection.device', self.device_combo.currentText())
            self.config.set('detection.half_precision', self.half_precision_check.isChecked())

            # Tracking settings
            self.config.set('tracking.max_age', self.max_age_spin.value())
            self.config.set('tracking.min_hits', self.min_hits_spin.value())
            self.config.set('tracking.iou_threshold', self.track_iou_spin.value())

            # Alert settings
            self.config.set('alerts.enabled', self.alerts_enabled_check.isChecked())
            self.config.set('alerts.email.enabled', self.email_enabled_check.isChecked())
            self.config.set('alerts.email.smtp_server', self.smtp_server_edit.text())
            self.config.set('alerts.email.smtp_port', self.smtp_port_spin.value())
            self.config.set('alerts.email.sender_email', self.sender_email_edit.text())
            self.config.set('alerts.sms.enabled', self.sms_enabled_check.isChecked())

            # Recording settings
            self.config.set('recording.enabled', self.recording_enabled_check.isChecked())
            self.config.set('recording.mode', self.recording_mode_combo.currentText())
            self.config.set('recording.codec', self.codec_combo.currentText())
            self.config.set('recording.quality', self.quality_combo.currentText())
            self.config.set('recording.pre_event_duration', self.pre_event_spin.value())
            self.config.set('recording.post_event_duration', self.post_event_spin.value())
            self.config.set('recording.max_storage_gb', self.storage_spin.value())

            # Save to file
            self.config.save()

            QMessageBox.information(
                self,
                "Success",
                "Settings saved successfully!\n\nPlease restart the system for changes to take effect."
            )

            logger.info("Settings saved")

        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def _reset_settings(self):
        """Reset settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Reset", "Settings reset functionality coming soon!")
