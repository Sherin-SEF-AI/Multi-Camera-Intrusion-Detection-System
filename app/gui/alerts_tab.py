"""
Alerts and Incidents Tab
View and manage security alerts and incidents.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLabel, QTextEdit, QGroupBox,
    QSplitter, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from datetime import datetime

from app.database.models import Event, Alert, Severity
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AlertsTab(QWidget):
    """
    Alerts and incidents management tab.
    """

    def __init__(self, system):
        super().__init__()

        self.system = system

        self._init_ui()
        self._load_events()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Top controls
        top_layout = QHBoxLayout()

        # Filter by severity
        top_layout.addWidget(QLabel("Severity:"))
        self.severity_filter = QComboBox()
        self.severity_filter.addItems([
            "All",
            "Critical",
            "High",
            "Medium",
            "Low"
        ])
        self.severity_filter.currentTextChanged.connect(self._filter_events)
        top_layout.addWidget(self.severity_filter)

        # Filter by status
        top_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems([
            "All",
            "Active",
            "Acknowledged",
            "Resolved"
        ])
        self.status_filter.currentTextChanged.connect(self._filter_events)
        top_layout.addWidget(self.status_filter)

        top_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._load_events)
        top_layout.addWidget(refresh_btn)

        layout.addLayout(top_layout)

        # Splitter for table and details
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Events table
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(7)
        self.events_table.setHorizontalHeaderLabels([
            "ID",
            "Timestamp",
            "Type",
            "Severity",
            "Camera",
            "Description",
            "Status"
        ])

        header = self.events_table.horizontalHeader()
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.events_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.events_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.events_table.setAlternatingRowColors(True)
        self.events_table.itemSelectionChanged.connect(self._show_event_details)

        splitter.addWidget(self.events_table)

        # Event details
        details_group = QGroupBox("Event Details")
        details_layout = QVBoxLayout(details_group)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        details_layout.addWidget(self.details_text)

        # Action buttons
        action_layout = QHBoxLayout()

        ack_btn = QPushButton("✓ Acknowledge")
        ack_btn.clicked.connect(self._acknowledge_event)
        action_layout.addWidget(ack_btn)

        resolve_btn = QPushButton("✓ Resolve")
        resolve_btn.clicked.connect(self._resolve_event)
        action_layout.addWidget(resolve_btn)

        false_pos_btn = QPushButton("⚠️ Mark False Positive")
        false_pos_btn.clicked.connect(self._mark_false_positive)
        action_layout.addWidget(false_pos_btn)

        action_layout.addStretch()

        view_video_btn = QPushButton("🎥 View Video")
        view_video_btn.clicked.connect(self._view_video)
        action_layout.addWidget(view_video_btn)

        details_layout.addLayout(action_layout)

        splitter.addWidget(details_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # Summary statistics
        stats_layout = QHBoxLayout()

        self.total_label = QLabel("Total: 0")
        self.critical_label = QLabel("Critical: 0")
        self.high_label = QLabel("High: 0")
        self.unresolved_label = QLabel("Unresolved: 0")

        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.critical_label)
        stats_layout.addWidget(self.high_label)
        stats_layout.addWidget(self.unresolved_label)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

    def _load_events(self):
        """Load events from database."""
        try:
            self.events_table.setRowCount(0)

            if not self.system.database:
                return

            with self.system.database.session_scope() as session:
                # Get recent events (last 100)
                events = session.query(Event).order_by(Event.timestamp.desc()).limit(100).all()

                stats = {'total': 0, 'critical': 0, 'high': 0, 'unresolved': 0}

                for event in events:
                    row = self.events_table.rowCount()
                    self.events_table.insertRow(row)

                    self.events_table.setItem(row, 0, QTableWidgetItem(str(event.id)))
                    self.events_table.setItem(row, 1, QTableWidgetItem(
                        event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    self.events_table.setItem(row, 2, QTableWidgetItem(event.event_type.value))
                    self.events_table.setItem(row, 3, QTableWidgetItem(event.severity.value))
                    self.events_table.setItem(row, 4, QTableWidgetItem(str(event.camera_id)))
                    self.events_table.setItem(row, 5, QTableWidgetItem(event.description))

                    # Status
                    if event.resolved:
                        status = "Resolved"
                        status_color = "#4caf50"
                    elif event.acknowledged:
                        status = "Acknowledged"
                        status_color = "#2196f3"
                    else:
                        status = "Active"
                        status_color = "#ff9800"

                    status_item = QTableWidgetItem(status)
                    status_item.setBackground(QColor(status_color))
                    self.events_table.setItem(row, 6, status_item)

                    # Severity color
                    severity_item = self.events_table.item(row, 3)
                    if event.severity == Severity.CRITICAL:
                        severity_item.setBackground(QColor("#f44336"))
                        stats['critical'] += 1
                    elif event.severity == Severity.HIGH:
                        severity_item.setBackground(QColor("#ff9800"))
                        stats['high'] += 1
                    elif event.severity == Severity.MEDIUM:
                        severity_item.setBackground(QColor("#ffeb3b"))
                    else:
                        severity_item.setBackground(QColor("#4caf50"))

                    stats['total'] += 1
                    if not event.resolved:
                        stats['unresolved'] += 1

                # Update statistics
                self.total_label.setText(f"Total: {stats['total']}")
                self.critical_label.setText(f"Critical: {stats['critical']}")
                self.high_label.setText(f"High: {stats['high']}")
                self.unresolved_label.setText(f"Unresolved: {stats['unresolved']}")

            logger.info(f"Loaded {self.events_table.rowCount()} events")

        except Exception as e:
            logger.error(f"Error loading events: {e}", exc_info=True)

    def _filter_events(self):
        """Filter events based on criteria."""
        severity = self.severity_filter.currentText()
        status = self.status_filter.currentText()

        for row in range(self.events_table.rowCount()):
            show = True

            # Severity filter
            if severity != "All":
                event_severity = self.events_table.item(row, 3).text()
                if severity.lower() != event_severity.lower():
                    show = False

            # Status filter
            if status != "All":
                event_status = self.events_table.item(row, 6).text()
                if status != event_status:
                    show = False

            self.events_table.setRowHidden(row, not show)

    def _show_event_details(self):
        """Show selected event details."""
        selected = self.events_table.selectedItems()
        if not selected:
            return

        try:
            event_id = int(self.events_table.item(selected[0].row(), 0).text())

            with self.system.database.session_scope() as session:
                event = session.query(Event).filter(Event.id == event_id).first()

                if event:
                    details = f"""
Event ID: {event.id}
Type: {event.event_type.value}
Severity: {event.severity.value}
Camera: {event.camera_id}
Timestamp: {event.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
Risk Score: {event.risk_score}

Description:
{event.description}

Status:
- Acknowledged: {'Yes' if event.acknowledged else 'No'}
- Acknowledged By: {event.acknowledged_by or 'N/A'}
- Resolved: {'Yes' if event.resolved else 'No'}
- False Positive: {'Yes' if event.false_positive else 'No'}

Files:
- Video: {event.video_path or 'N/A'}
- Snapshot: {event.snapshot_path or 'N/A'}

Notes:
{event.resolution_notes or 'No notes'}
                    """

                    self.details_text.setPlainText(details.strip())

        except Exception as e:
            logger.error(f"Error showing event details: {e}")

    def _acknowledge_event(self):
        """Acknowledge selected event."""
        selected = self.events_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an event!")
            return

        try:
            event_id = int(self.events_table.item(selected[0].row(), 0).text())

            with self.system.database.session_scope() as session:
                event = session.query(Event).filter(Event.id == event_id).first()

                if event:
                    event.acknowledged = True
                    event.acknowledged_by = "System Admin"  # TODO: Get actual user
                    event.acknowledged_at = datetime.utcnow()

            self._load_events()
            QMessageBox.information(self, "Success", "Event acknowledged!")

        except Exception as e:
            logger.error(f"Error acknowledging event: {e}")
            QMessageBox.critical(self, "Error", f"Failed to acknowledge event: {e}")

    def _resolve_event(self):
        """Resolve selected event."""
        selected = self.events_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an event!")
            return

        try:
            event_id = int(self.events_table.item(selected[0].row(), 0).text())

            with self.system.database.session_scope() as session:
                event = session.query(Event).filter(Event.id == event_id).first()

                if event:
                    event.resolved = True
                    event.resolved_at = datetime.utcnow()

            self._load_events()
            QMessageBox.information(self, "Success", "Event resolved!")

        except Exception as e:
            logger.error(f"Error resolving event: {e}")
            QMessageBox.critical(self, "Error", f"Failed to resolve event: {e}")

    def _mark_false_positive(self):
        """Mark event as false positive."""
        selected = self.events_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an event!")
            return

        try:
            event_id = int(self.events_table.item(selected[0].row(), 0).text())

            with self.system.database.session_scope() as session:
                event = session.query(Event).filter(Event.id == event_id).first()

                if event:
                    event.false_positive = True
                    event.resolved = True
                    event.resolved_at = datetime.utcnow()
                    event.resolution_notes = "Marked as false positive"

            self._load_events()
            QMessageBox.information(self, "Success", "Event marked as false positive!")

        except Exception as e:
            logger.error(f"Error marking false positive: {e}")
            QMessageBox.critical(self, "Error", f"Failed to mark false positive: {e}")

    def _view_video(self):
        """View event video."""
        QMessageBox.information(self, "Info", "Video viewer coming soon!")
