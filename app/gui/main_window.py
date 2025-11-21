"""
Main Window - PyQt6 GUI
Professional dark-themed interface for multi-camera intrusion detection.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QStatusBar, QPushButton, QMenuBar, QMenu, QToolBar,
    QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QIcon, QFont
from datetime import datetime
import psutil

from app.utils.logger import get_logger
from app.gui.live_monitoring_tab import LiveMonitoringTab
from app.gui.person_database_tab import PersonDatabaseTab
from app.gui.settings_tab import SettingsTab
from app.gui.analytics_tab import AnalyticsTab
from app.gui.alerts_tab import AlertsTab

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    Main application window with tabbed interface.

    Features:
    - Multi-camera live monitoring
    - Person database management
    - Settings and configuration
    - Analytics and reporting
    - Alerts and incidents
    """

    # Signals
    shutdown_requested = pyqtSignal()

    def __init__(self, system):
        """
        Initialize main window.

        Args:
            system: IntrusionDetectionSystem instance
        """
        super().__init__()

        self.system = system
        self.config = system.config

        # Window properties
        self.setWindowTitle("Advanced Multi-Camera Intrusion Detection System")
        self.setMinimumSize(1400, 900)

        # Apply dark theme
        self._apply_dark_theme()

        # Initialize UI
        self._init_ui()

        # Setup menu bar
        self._create_menu_bar()

        # Setup toolbar
        self._create_toolbar()

        # Setup status bar
        self._create_status_bar()

        # Start update timers
        self._start_timers()

        logger.info("Main window initialized")

    def _apply_dark_theme(self):
        """Apply modern dark theme to the application."""
        dark_stylesheet = """
        QMainWindow {
            background-color: #1e1e1e;
        }

        QWidget {
            background-color: #1e1e1e;
            color: #e0e0e0;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10pt;
        }

        QTabWidget::pane {
            border: 1px solid #3d3d3d;
            background-color: #252525;
        }

        QTabBar::tab {
            background-color: #2d2d2d;
            color: #e0e0e0;
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid #3d3d3d;
            border-bottom: none;
        }

        QTabBar::tab:selected {
            background-color: #0d47a1;
            color: white;
        }

        QTabBar::tab:hover {
            background-color: #3d3d3d;
        }

        QPushButton {
            background-color: #0d47a1;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
        }

        QPushButton:hover {
            background-color: #1565c0;
        }

        QPushButton:pressed {
            background-color: #0a3d91;
        }

        QPushButton:disabled {
            background-color: #424242;
            color: #757575;
        }

        QLabel {
            color: #e0e0e0;
        }

        QGroupBox {
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }

        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #2d2d2d;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 4px;
            color: #e0e0e0;
        }

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border: 1px solid #0d47a1;
        }

        QComboBox {
            background-color: #2d2d2d;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 4px;
            color: #e0e0e0;
        }

        QComboBox::drop-down {
            border: none;
        }

        QComboBox::down-arrow {
            image: url(down_arrow.png);
            width: 12px;
            height: 12px;
        }

        QListWidget, QTreeWidget, QTableWidget {
            background-color: #252525;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            color: #e0e0e0;
        }

        QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {
            background-color: #0d47a1;
        }

        QHeaderView::section {
            background-color: #2d2d2d;
            color: #e0e0e0;
            padding: 4px;
            border: 1px solid #3d3d3d;
            font-weight: bold;
        }

        QScrollBar:vertical {
            background-color: #2d2d2d;
            width: 12px;
            border-radius: 6px;
        }

        QScrollBar::handle:vertical {
            background-color: #5d5d5d;
            border-radius: 6px;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #6d6d6d;
        }

        QScrollBar:horizontal {
            background-color: #2d2d2d;
            height: 12px;
            border-radius: 6px;
        }

        QScrollBar::handle:horizontal {
            background-color: #5d5d5d;
            border-radius: 6px;
            min-width: 20px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #6d6d6d;
        }

        QMenuBar {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border-bottom: 1px solid #3d3d3d;
        }

        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }

        QMenuBar::item:selected {
            background-color: #3d3d3d;
        }

        QMenu {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border: 1px solid #3d3d3d;
        }

        QMenu::item:selected {
            background-color: #0d47a1;
        }

        QStatusBar {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border-top: 1px solid #3d3d3d;
        }

        QToolBar {
            background-color: #2d2d2d;
            border-bottom: 1px solid #3d3d3d;
            spacing: 4px;
            padding: 4px;
        }

        QToolButton {
            background-color: transparent;
            border: none;
            padding: 4px;
            border-radius: 4px;
        }

        QToolButton:hover {
            background-color: #3d3d3d;
        }

        QToolButton:pressed {
            background-color: #0d47a1;
        }

        QSlider::groove:horizontal {
            border: 1px solid #3d3d3d;
            height: 4px;
            background: #2d2d2d;
            border-radius: 2px;
        }

        QSlider::handle:horizontal {
            background: #0d47a1;
            border: 1px solid #0d47a1;
            width: 14px;
            margin: -6px 0;
            border-radius: 7px;
        }

        QSlider::handle:horizontal:hover {
            background: #1565c0;
        }

        QCheckBox {
            spacing: 5px;
        }

        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #3d3d3d;
            border-radius: 3px;
            background-color: #2d2d2d;
        }

        QCheckBox::indicator:checked {
            background-color: #0d47a1;
            border: 1px solid #0d47a1;
        }

        QRadioButton::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #3d3d3d;
            border-radius: 9px;
            background-color: #2d2d2d;
        }

        QRadioButton::indicator:checked {
            background-color: #0d47a1;
            border: 1px solid #0d47a1;
        }

        QProgressBar {
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            text-align: center;
            background-color: #2d2d2d;
        }

        QProgressBar::chunk {
            background-color: #0d47a1;
            border-radius: 3px;
        }
        """

        self.setStyleSheet(dark_stylesheet)

    def _init_ui(self):
        """Initialize the user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = self._create_header()
        main_layout.addWidget(header)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Create tabs
        self.live_monitoring_tab = LiveMonitoringTab(self.system)
        self.person_database_tab = PersonDatabaseTab(self.system)
        self.alerts_tab = AlertsTab(self.system)
        self.analytics_tab = AnalyticsTab(self.system)
        self.settings_tab = SettingsTab(self.system)

        # Add tabs
        self.tabs.addTab(self.live_monitoring_tab, "🎥 Live Monitoring")
        self.tabs.addTab(self.person_database_tab, "👥 Person Database")
        self.tabs.addTab(self.alerts_tab, "🚨 Alerts & Incidents")
        self.tabs.addTab(self.analytics_tab, "📊 Analytics")
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")

        main_layout.addWidget(self.tabs)

    def _create_header(self):
        """Create header with logo and system status."""
        header = QWidget()
        header.setMaximumHeight(80)
        header.setStyleSheet("background-color: #0d47a1; border-bottom: 2px solid #1565c0;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)

        # Title
        title_label = QLabel("🛡️ Advanced Multi-Camera Intrusion Detection System")
        title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white;")
        layout.addWidget(title_label)

        layout.addStretch()

        # System status indicators
        self.system_status_widget = self._create_system_status()
        layout.addWidget(self.system_status_widget)

        return header

    def _create_system_status(self):
        """Create system status indicators."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        # Time
        self.time_label = QLabel()
        self.time_label.setStyleSheet("color: white; font-size: 12pt; font-weight: bold;")
        layout.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignRight)

        # System info
        self.system_info_label = QLabel()
        self.system_info_label.setStyleSheet("color: #e0e0e0; font-size: 9pt;")
        layout.addWidget(self.system_info_label, alignment=Qt.AlignmentFlag.AlignRight)

        return widget

    def _create_menu_bar(self):
        """Create application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        export_action = QAction("📤 Export Data", self)
        export_action.triggered.connect(self._export_data)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("❌ Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        fullscreen_action = QAction("🖥️ Toggle Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        db_optimize_action = QAction("🗄️ Optimize Database", self)
        db_optimize_action.triggered.connect(self._optimize_database)
        tools_menu.addAction(db_optimize_action)

        backup_action = QAction("💾 Backup Database", self)
        backup_action.triggered.connect(self._backup_database)
        tools_menu.addAction(backup_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("ℹ️ About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self):
        """Create application toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Start/Stop button
        self.start_stop_btn = QPushButton("▶️ Start System")
        self.start_stop_btn.clicked.connect(self._toggle_system)
        toolbar.addWidget(self.start_stop_btn)

        toolbar.addSeparator()

        # Screenshot button
        screenshot_btn = QPushButton("📸 Screenshot")
        screenshot_btn.clicked.connect(self._take_screenshot)
        toolbar.addWidget(screenshot_btn)

        # Record button
        self.record_btn = QPushButton("⏺️ Start Recording")
        self.record_btn.clicked.connect(self._toggle_recording)
        toolbar.addWidget(self.record_btn)

        toolbar.addSeparator()

        # Emergency alert
        emergency_btn = QPushButton("🚨 Emergency Alert")
        emergency_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        emergency_btn.clicked.connect(self._trigger_emergency_alert)
        toolbar.addWidget(emergency_btn)

    def _create_status_bar(self):
        """Create status bar with system information."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status labels
        self.camera_status_label = QLabel("📷 Cameras: 0/0")
        self.detection_status_label = QLabel("🔍 Detections: 0")
        self.tracking_status_label = QLabel("🎯 Active Tracks: 0")
        self.fps_label = QLabel("⚡ FPS: 0.0")

        self.status_bar.addPermanentWidget(self.camera_status_label)
        self.status_bar.addPermanentWidget(self.detection_status_label)
        self.status_bar.addPermanentWidget(self.tracking_status_label)
        self.status_bar.addPermanentWidget(self.fps_label)

        self.status_bar.showMessage("System ready")

    def _start_timers(self):
        """Start update timers."""
        # Time update timer (1 second)
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start(1000)

        # System stats timer (2 seconds)
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_system_stats)
        self.stats_timer.start(2000)

        # Initial update
        self._update_time()
        self._update_system_stats()

    def _update_time(self):
        """Update time display."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(current_time)

    def _update_system_stats(self):
        """Update system statistics."""
        # CPU and Memory
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory().percent

        self.system_info_label.setText(f"CPU: {cpu:.1f}% | RAM: {memory:.1f}%")

        # Camera status
        if self.system.camera_manager:
            cameras = self.system.camera_manager.get_all_cameras()
            active_cameras = sum(1 for cam in cameras.values() if cam.is_connected)
            self.camera_status_label.setText(f"📷 Cameras: {active_cameras}/{len(cameras)}")

        # Detection status
        if self.system.detection_engine:
            stats = self.system.detection_engine.get_statistics()
            self.fps_label.setText(f"⚡ FPS: {stats.get('inference_fps', 0):.1f}")

        # Tracking status
        total_tracks = 0
        if self.system.tracking_engines:
            for tracker in self.system.tracking_engines.values():
                stats = tracker.get_statistics()
                total_tracks += stats.get('active_tracks', 0)

        self.tracking_status_label.setText(f"🎯 Active Tracks: {total_tracks}")

    def _toggle_system(self):
        """Toggle system start/stop."""
        if self.system.is_running:
            self._stop_system()
        else:
            self._start_system()

    def _start_system(self):
        """Start the detection system."""
        try:
            if self.system.start():
                self.start_stop_btn.setText("⏸️ Stop System")
                self.status_bar.showMessage("System started successfully", 3000)
                logger.info("System started from GUI")
            else:
                QMessageBox.critical(self, "Error", "Failed to start system. Check logs for details.")
        except Exception as e:
            logger.error(f"Error starting system: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to start system: {e}")

    def _stop_system(self):
        """Stop the detection system."""
        try:
            self.system.stop()
            self.start_stop_btn.setText("▶️ Start System")
            self.status_bar.showMessage("System stopped", 3000)
            logger.info("System stopped from GUI")
        except Exception as e:
            logger.error(f"Error stopping system: {e}", exc_info=True)

    def _toggle_recording(self):
        """Toggle video recording."""
        # TODO: Implement recording toggle
        if self.record_btn.text() == "⏺️ Start Recording":
            self.record_btn.setText("⏹️ Stop Recording")
            self.status_bar.showMessage("Recording started", 3000)
        else:
            self.record_btn.setText("⏺️ Start Recording")
            self.status_bar.showMessage("Recording stopped", 3000)

    def _take_screenshot(self):
        """Take screenshot of current view."""
        self.status_bar.showMessage("Screenshot saved", 3000)
        # TODO: Implement screenshot functionality

    def _trigger_emergency_alert(self):
        """Trigger emergency alert."""
        reply = QMessageBox.question(
            self,
            "Emergency Alert",
            "Trigger emergency alert to all channels?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.status_bar.showMessage("Emergency alert triggered!", 5000)
            logger.critical("Emergency alert triggered from GUI")
            # TODO: Implement emergency alert

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _export_data(self):
        """Export system data."""
        QMessageBox.information(self, "Export", "Data export functionality coming soon!")

    def _optimize_database(self):
        """Optimize database."""
        try:
            if self.system.database:
                self.system.database.optimize()
                QMessageBox.information(self, "Success", "Database optimized successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to optimize database: {e}")

    def _backup_database(self):
        """Backup database."""
        try:
            if self.system.database:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"backups/database_backup_{timestamp}.db"
                self.system.database.backup(backup_path)
                QMessageBox.information(self, "Success", f"Database backed up to:\n{backup_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to backup database: {e}")

    def _show_about(self):
        """Show about dialog."""
        about_text = """
        <h2>Advanced Multi-Camera Intrusion Detection System</h2>
        <p><b>Version:</b> 1.0.0</p>
        <p><b>Description:</b> Enterprise-grade security monitoring with AI-powered detection</p>
        <br>
        <p><b>Features:</b></p>
        <ul>
            <li>Multi-camera real-time monitoring</li>
            <li>YOLOv8 person detection</li>
            <li>Multi-object tracking</li>
            <li>Person re-identification</li>
            <li>Behavioral analysis</li>
            <li>Threat assessment</li>
            <li>Alert system</li>
        </ul>
        <br>
        <p><b>Technology Stack:</b> Python, PyQt6, OpenCV, PyTorch, YOLOv8</p>
        <p><b>License:</b> MIT</p>
        """

        QMessageBox.about(self, "About", about_text)

    def closeEvent(self, event):
        """Handle window close event."""
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit?\nThis will stop all monitoring and recording.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Application closing...")

            # Stop system
            if self.system.is_running:
                self.system.stop()

            # Emit shutdown signal
            self.shutdown_requested.emit()

            event.accept()
        else:
            event.ignore()
