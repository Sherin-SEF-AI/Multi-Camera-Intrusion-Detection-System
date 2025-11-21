"""
Analytics Tab
System analytics, statistics, and reporting.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from datetime import datetime, timedelta

from app.database.models import Event, Person, Detection
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StatCard(QGroupBox):
    """Card widget for displaying a statistic."""

    def __init__(self, title, value, icon=""):
        super().__init__()

        self.setMaximumHeight(120)

        layout = QVBoxLayout(self)

        # Icon and title
        title_layout = QHBoxLayout()
        title_label = QLabel(f"{icon} {title}")
        title_label.setFont(QFont("Segoe UI", 10))
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Value
        self.value_label = QLabel(str(value))
        self.value_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #0d47a1;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

    def update_value(self, value):
        """Update the displayed value."""
        self.value_label.setText(str(value))


class AnalyticsTab(QWidget):
    """
    Analytics and reporting tab.
    """

    def __init__(self, system):
        super().__init__()

        self.system = system

        self._init_ui()

        # Start update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_analytics)
        self.update_timer.start(5000)  # Update every 5 seconds

        self._update_analytics()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Time range selector
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Time Range:"))

        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems([
            "Today",
            "Last 7 Days",
            "Last 30 Days",
            "All Time"
        ])
        self.time_range_combo.currentTextChanged.connect(self._update_analytics)
        top_layout.addWidget(self.time_range_combo)

        top_layout.addStretch()

        export_btn = QPushButton("📊 Export Report")
        export_btn.clicked.connect(self._export_report)
        top_layout.addWidget(export_btn)

        layout.addLayout(top_layout)

        # Statistics cards
        stats_layout = QHBoxLayout()

        self.total_detections_card = StatCard("Total Detections", "0", "🔍")
        stats_layout.addWidget(self.total_detections_card)

        self.unique_persons_card = StatCard("Unique Persons", "0", "👥")
        stats_layout.addWidget(self.unique_persons_card)

        self.total_events_card = StatCard("Total Events", "0", "🚨")
        stats_layout.addWidget(self.total_events_card)

        self.critical_events_card = StatCard("Critical Events", "0", "⚠️")
        stats_layout.addWidget(self.critical_events_card)

        layout.addLayout(stats_layout)

        # Camera performance
        camera_group = QGroupBox("Camera Performance")
        camera_layout = QVBoxLayout(camera_group)

        self.camera_table = QTableWidget()
        self.camera_table.setColumnCount(5)
        self.camera_table.setHorizontalHeaderLabels([
            "Camera",
            "Detections",
            "Events",
            "Uptime %",
            "Avg FPS"
        ])
        self.camera_table.setMaximumHeight(200)
        camera_layout.addWidget(self.camera_table)

        layout.addWidget(camera_group)

        # Top persons
        persons_group = QGroupBox("Most Frequent Persons")
        persons_layout = QVBoxLayout(persons_group)

        self.persons_table = QTableWidget()
        self.persons_table.setColumnCount(4)
        self.persons_table.setHorizontalHeaderLabels([
            "Name",
            "Authorization",
            "Appearances",
            "Last Seen"
        ])
        self.persons_table.setMaximumHeight(200)
        persons_layout.addWidget(self.persons_table)

        layout.addWidget(persons_group)

        # Event breakdown
        events_group = QGroupBox("Event Breakdown")
        events_layout = QVBoxLayout(events_group)

        self.events_table = QTableWidget()
        self.events_table.setColumnCount(3)
        self.events_table.setHorizontalHeaderLabels([
            "Event Type",
            "Count",
            "Percentage"
        ])
        self.events_table.setMaximumHeight(200)
        events_layout.addWidget(self.events_table)

        layout.addWidget(events_group)

        layout.addStretch()

    def _update_analytics(self):
        """Update analytics data."""
        try:
            if not self.system.database:
                return

            with self.system.database.session_scope() as session:
                # Get time range
                time_range = self._get_time_range()

                # Total detections
                if time_range:
                    total_detections = session.query(Detection).filter(
                        Detection.timestamp >= time_range
                    ).count()
                else:
                    total_detections = session.query(Detection).count()

                self.total_detections_card.update_value(total_detections)

                # Unique persons
                unique_persons = session.query(Person).count()
                self.unique_persons_card.update_value(unique_persons)

                # Total events
                if time_range:
                    total_events = session.query(Event).filter(
                        Event.timestamp >= time_range
                    ).count()

                    critical_events = session.query(Event).filter(
                        Event.timestamp >= time_range,
                        Event.severity == 'critical'
                    ).count()
                else:
                    total_events = session.query(Event).count()
                    critical_events = session.query(Event).filter(
                        Event.severity == 'critical'
                    ).count()

                self.total_events_card.update_value(total_events)
                self.critical_events_card.update_value(critical_events)

                # Update camera performance
                self._update_camera_performance()

                # Update top persons
                self._update_top_persons()

        except Exception as e:
            logger.error(f"Error updating analytics: {e}")

    def _get_time_range(self):
        """Get time range filter."""
        range_text = self.time_range_combo.currentText()

        if range_text == "Today":
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif range_text == "Last 7 Days":
            return datetime.now() - timedelta(days=7)
        elif range_text == "Last 30 Days":
            return datetime.now() - timedelta(days=30)
        else:
            return None

    def _update_camera_performance(self):
        """Update camera performance table."""
        self.camera_table.setRowCount(0)

        if self.system.camera_manager:
            cameras = self.system.camera_manager.get_all_cameras()

            for cam_id, camera in cameras.items():
                row = self.camera_table.rowCount()
                self.camera_table.insertRow(row)

                info = camera.get_info()

                self.camera_table.setItem(row, 0, QTableWidgetItem(info.name))
                self.camera_table.setItem(row, 1, QTableWidgetItem("0"))  # TODO: Get from DB
                self.camera_table.setItem(row, 2, QTableWidgetItem("0"))  # TODO: Get from DB
                self.camera_table.setItem(row, 3, QTableWidgetItem("100%"))  # TODO: Calculate
                self.camera_table.setItem(row, 4, QTableWidgetItem(f"{info.current_fps:.1f}"))

    def _update_top_persons(self):
        """Update top persons table."""
        self.persons_table.setRowCount(0)

        try:
            if not self.system.database:
                return

            with self.system.database.session_scope() as session:
                # Get top 10 persons by appearance count
                persons = session.query(Person).order_by(
                    Person.appearance_count.desc()
                ).limit(10).all()

                for person in persons:
                    row = self.persons_table.rowCount()
                    self.persons_table.insertRow(row)

                    self.persons_table.setItem(row, 0, QTableWidgetItem(person.name))
                    self.persons_table.setItem(row, 1, QTableWidgetItem(
                        person.authorization_level.value
                    ))
                    self.persons_table.setItem(row, 2, QTableWidgetItem(
                        str(person.appearance_count)
                    ))

                    last_seen = person.last_seen.strftime("%Y-%m-%d %H:%M") if person.last_seen else "Never"
                    self.persons_table.setItem(row, 3, QTableWidgetItem(last_seen))

        except Exception as e:
            logger.error(f"Error updating top persons: {e}")

    def _export_report(self):
        """Export analytics report."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Export", "Report export functionality coming soon!")
