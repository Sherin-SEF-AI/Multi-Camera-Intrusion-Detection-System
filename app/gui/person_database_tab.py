"""
Person Database Tab
Manage known persons and perform re-identification.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QLabel, QGroupBox, QComboBox,
    QDialog, QFormLayout, QTextEdit, QFileDialog, QMessageBox,
    QHeaderView, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage, QColor
import cv2
from datetime import datetime

from app.database.models import Person, AuthorizationLevel
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AddPersonDialog(QDialog):
    """Dialog for adding a new person to the database."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Add New Person")
        self.setMinimumSize(400, 500)

        self.photo_path = None

        layout = QFormLayout(self)

        # Name
        self.name_edit = QLineEdit()
        layout.addRow("Name*:", self.name_edit)

        # Authorization level
        self.auth_combo = QComboBox()
        self.auth_combo.addItems([
            "Authorized",
            "Visitor",
            "Unknown",
            "Blacklist"
        ])
        layout.addRow("Authorization Level*:", self.auth_combo)

        # Email
        self.email_edit = QLineEdit()
        layout.addRow("Email:", self.email_edit)

        # Phone
        self.phone_edit = QLineEdit()
        layout.addRow("Phone:", self.phone_edit)

        # Department
        self.department_edit = QLineEdit()
        layout.addRow("Department:", self.department_edit)

        # Access Level
        self.access_level_combo = QComboBox()
        self.access_level_combo.addItems(["0 - No Access", "1 - Basic", "2 - Medium", "3 - High", "4 - Full"])
        layout.addRow("Access Level:", self.access_level_combo)

        # Photo
        photo_layout = QHBoxLayout()
        self.photo_label = QLabel("No photo selected")
        photo_layout.addWidget(self.photo_label)

        select_photo_btn = QPushButton("Select Photo")
        select_photo_btn.clicked.connect(self._select_photo)
        photo_layout.addWidget(select_photo_btn)

        layout.addRow("Photo:", photo_layout)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        layout.addRow("Notes:", self.notes_edit)

        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addRow("", button_layout)

    def _select_photo(self):
        """Select photo file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Photo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            self.photo_path = file_path
            self.photo_label.setText(f"Selected: {file_path.split('/')[-1]}")

    def get_person_data(self):
        """Get person data from form."""
        auth_level_map = {
            "Authorized": AuthorizationLevel.AUTHORIZED,
            "Visitor": AuthorizationLevel.VISITOR,
            "Unknown": AuthorizationLevel.UNKNOWN,
            "Blacklist": AuthorizationLevel.BLACKLIST
        }

        return {
            'name': self.name_edit.text(),
            'authorization_level': auth_level_map[self.auth_combo.currentText()],
            'email': self.email_edit.text() or None,
            'phone': self.phone_edit.text() or None,
            'department': self.department_edit.text() or None,
            'access_level': self.access_level_combo.currentIndex(),
            'notes': self.notes_edit.toPlainText() or None,
            'photo_path': self.photo_path
        }


class PersonDatabaseTab(QWidget):
    """
    Person database management tab.
    """

    def __init__(self, system):
        super().__init__()

        self.system = system

        self._init_ui()
        self._load_persons()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Top controls
        top_layout = QHBoxLayout()

        # Search
        top_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name, email, phone...")
        self.search_edit.textChanged.connect(self._filter_persons)
        top_layout.addWidget(self.search_edit)

        # Filter by authorization
        top_layout.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All",
            "Authorized",
            "Visitors",
            "Unknown",
            "Blacklist"
        ])
        self.filter_combo.currentTextChanged.connect(self._filter_persons)
        top_layout.addWidget(self.filter_combo)

        top_layout.addStretch()

        # Add person button
        add_btn = QPushButton("➕ Add Person")
        add_btn.clicked.connect(self._add_person)
        top_layout.addWidget(add_btn)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._load_persons)
        top_layout.addWidget(refresh_btn)

        layout.addLayout(top_layout)

        # Table
        self.persons_table = QTableWidget()
        self.persons_table.setColumnCount(8)
        self.persons_table.setHorizontalHeaderLabels([
            "ID",
            "Name",
            "Authorization",
            "Email",
            "Phone",
            "Department",
            "Last Seen",
            "Appearances"
        ])

        # Make table look better
        header = self.persons_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.persons_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.persons_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.persons_table.setAlternatingRowColors(True)

        layout.addWidget(self.persons_table)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        view_btn = QPushButton("👁️ View Details")
        view_btn.clicked.connect(self._view_person)
        bottom_layout.addWidget(view_btn)

        edit_btn = QPushButton("✏️ Edit")
        edit_btn.clicked.connect(self._edit_person)
        bottom_layout.addWidget(edit_btn)

        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.setStyleSheet("background-color: #d32f2f;")
        delete_btn.clicked.connect(self._delete_person)
        bottom_layout.addWidget(delete_btn)

        bottom_layout.addStretch()

        export_btn = QPushButton("📤 Export List")
        export_btn.clicked.connect(self._export_persons)
        bottom_layout.addWidget(export_btn)

        import_btn = QPushButton("📥 Import List")
        import_btn.clicked.connect(self._import_persons)
        bottom_layout.addWidget(import_btn)

        layout.addLayout(bottom_layout)

    def _load_persons(self):
        """Load persons from database."""
        try:
            self.persons_table.setRowCount(0)

            if not self.system.database:
                return

            with self.system.database.session_scope() as session:
                persons = session.query(Person).all()

                for person in persons:
                    row = self.persons_table.rowCount()
                    self.persons_table.insertRow(row)

                    self.persons_table.setItem(row, 0, QTableWidgetItem(str(person.id)))
                    self.persons_table.setItem(row, 1, QTableWidgetItem(person.name))
                    self.persons_table.setItem(row, 2, QTableWidgetItem(person.authorization_level.value))
                    self.persons_table.setItem(row, 3, QTableWidgetItem(person.email or ""))
                    self.persons_table.setItem(row, 4, QTableWidgetItem(person.phone or ""))
                    self.persons_table.setItem(row, 5, QTableWidgetItem(person.department or ""))

                    last_seen = person.last_seen.strftime("%Y-%m-%d %H:%M") if person.last_seen else "Never"
                    self.persons_table.setItem(row, 6, QTableWidgetItem(last_seen))
                    self.persons_table.setItem(row, 7, QTableWidgetItem(str(person.appearance_count)))

                    # Color code by authorization level
                    auth_level = person.authorization_level.value
                    if auth_level == "authorized":
                        color = "#4caf50"  # Green
                    elif auth_level == "visitor":
                        color = "#2196f3"  # Blue
                    elif auth_level == "blacklist":
                        color = "#f44336"  # Red
                    else:
                        color = "#9e9e9e"  # Gray

                    self.persons_table.item(row, 2).setBackground(QColor(color))

            logger.info(f"Loaded {self.persons_table.rowCount()} persons")

        except Exception as e:
            logger.error(f"Error loading persons: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load persons: {e}")

    def _filter_persons(self):
        """Filter persons based on search and filter criteria."""
        search_text = self.search_edit.text().lower()
        filter_text = self.filter_combo.currentText()

        for row in range(self.persons_table.rowCount()):
            show = True

            # Search filter
            if search_text:
                name = self.persons_table.item(row, 1).text().lower()
                email = self.persons_table.item(row, 3).text().lower()
                phone = self.persons_table.item(row, 4).text().lower()

                if search_text not in name and search_text not in email and search_text not in phone:
                    show = False

            # Authorization filter
            if filter_text != "All":
                auth = self.persons_table.item(row, 2).text().lower()
                if filter_text.lower() not in auth:
                    show = False

            self.persons_table.setRowHidden(row, not show)

    def _add_person(self):
        """Add new person to database."""
        dialog = AddPersonDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                person_data = dialog.get_person_data()

                if not person_data['name']:
                    QMessageBox.warning(self, "Warning", "Name is required!")
                    return

                # Create person
                person = Person(
                    name=person_data['name'],
                    authorization_level=person_data['authorization_level'],
                    email=person_data['email'],
                    phone=person_data['phone'],
                    department=person_data['department'],
                    access_level=person_data['access_level'],
                    notes=person_data['notes']
                )

                # TODO: Process photo and extract features

                # Save to database
                self.system.database.add(person)

                QMessageBox.information(self, "Success", f"Person '{person.name}' added successfully!")
                self._load_persons()

            except Exception as e:
                logger.error(f"Error adding person: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to add person: {e}")

    def _view_person(self):
        """View person details."""
        selected = self.persons_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a person!")
            return

        person_id = int(self.persons_table.item(selected[0].row(), 0).text())

        # TODO: Show detailed person information dialog

        QMessageBox.information(self, "Info", f"View details for person ID: {person_id}")

    def _edit_person(self):
        """Edit person information."""
        selected = self.persons_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a person!")
            return

        # TODO: Implement edit dialog

        QMessageBox.information(self, "Info", "Edit functionality coming soon!")

    def _delete_person(self):
        """Delete person from database."""
        selected = self.persons_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a person!")
            return

        person_name = self.persons_table.item(selected[0].row(), 1).text()
        person_id = int(self.persons_table.item(selected[0].row(), 0).text())

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{person_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                with self.system.database.session_scope() as session:
                    person = session.query(Person).filter(Person.id == person_id).first()
                    if person:
                        session.delete(person)

                QMessageBox.information(self, "Success", f"Person '{person_name}' deleted!")
                self._load_persons()

            except Exception as e:
                logger.error(f"Error deleting person: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to delete person: {e}")

    def _export_persons(self):
        """Export persons list."""
        QMessageBox.information(self, "Export", "Export functionality coming soon!")

    def _import_persons(self):
        """Import persons list."""
        QMessageBox.information(self, "Import", "Import functionality coming soon!")
