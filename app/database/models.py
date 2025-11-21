"""
Database Models
SQLAlchemy ORM models for the intrusion detection system.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey,
    JSON, LargeBinary, Enum, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class AuthorizationLevel(enum.Enum):
    """Authorization levels for persons."""
    AUTHORIZED = "authorized"
    VISITOR = "visitor"
    UNKNOWN = "unknown"
    BLACKLIST = "blacklist"


class EventType(enum.Enum):
    """Types of security events."""
    INTRUSION = "intrusion"
    LOITERING = "loitering"
    ANOMALY = "anomaly"
    THREAT = "threat"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    AGGRESSIVE_BEHAVIOR = "aggressive_behavior"
    FALL_DETECTED = "fall_detected"
    CROWD_ANOMALY = "crowd_anomaly"
    ZONE_VIOLATION = "zone_violation"
    BLACKLIST_DETECTED = "blacklist_detected"
    AFTER_HOURS = "after_hours"
    OVERSTAY = "overstay"


class Severity(enum.Enum):
    """Event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(enum.Enum):
    """Types of alerts."""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    SYSTEM = "system"
    PUSH = "push"


class AlertStatus(enum.Enum):
    """Alert delivery status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class ZoneType(enum.Enum):
    """Types of monitoring zones."""
    RESTRICTED = "restricted"
    MONITORED = "monitored"
    ENTRANCE = "entrance"
    EXIT = "exit"
    PERIMETER = "perimeter"
    LOITERING = "loitering"


class LogLevel(enum.Enum):
    """System log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Person(Base):
    """
    Person model for storing known individuals.
    Used for re-identification and access control.
    """
    __tablename__ = 'persons'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    photos = Column(JSON, default=list)  # List of file paths to person images
    feature_vector = Column(LargeBinary, nullable=True)  # Serialized numpy array
    authorization_level = Column(
        Enum(AuthorizationLevel),
        default=AuthorizationLevel.UNKNOWN,
        nullable=False,
        index=True
    )
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    appearance_count = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    department = Column(String(255), nullable=True)
    access_level = Column(Integer, default=0)  # Numeric access level
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    detections = relationship("Detection", back_populates="person", cascade="all, delete-orphan")
    tracks = relationship("Track", back_populates="person")
    events = relationship("Event", back_populates="person")

    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.name}', level={self.authorization_level.value})>"


class Detection(Base):
    """
    Detection model for storing individual person detections.
    """
    __tablename__ = 'detections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, nullable=False, index=True)
    person_id = Column(Integer, ForeignKey('persons.id'), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_w = Column(Integer, nullable=False)
    bbox_h = Column(Integer, nullable=False)
    frame_path = Column(String(512), nullable=True)
    track_id = Column(Integer, nullable=True, index=True)
    feature_vector = Column(LargeBinary, nullable=True)

    # Relationships
    person = relationship("Person", back_populates="detections")

    # Index for efficient queries
    __table_args__ = (
        Index('idx_camera_timestamp', 'camera_id', 'timestamp'),
        Index('idx_person_timestamp', 'person_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<Detection(id={self.id}, camera={self.camera_id}, track={self.track_id})>"


class Track(Base):
    """
    Track model for storing person tracking information.
    """
    __tablename__ = 'tracks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, nullable=False, index=True)
    track_id = Column(Integer, nullable=False, index=True)
    person_id = Column(Integer, ForeignKey('persons.id'), nullable=True, index=True)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    trajectory = Column(JSON, default=list)  # List of (x, y) coordinates
    total_frames = Column(Integer, default=0)
    average_speed = Column(Float, default=0.0)
    max_speed = Column(Float, default=0.0)
    distance_traveled = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)

    # Relationships
    person = relationship("Person", back_populates="tracks")

    # Index for efficient queries
    __table_args__ = (
        Index('idx_camera_track', 'camera_id', 'track_id'),
        Index('idx_camera_time', 'camera_id', 'start_time'),
    )

    def __repr__(self):
        return f"<Track(id={self.id}, camera={self.camera_id}, track_id={self.track_id})>"


class Event(Base):
    """
    Event model for storing security events and incidents.
    """
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(Enum(EventType), nullable=False, index=True)
    camera_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    severity = Column(Enum(Severity), nullable=False, index=True)
    description = Column(Text, nullable=False)
    person_id = Column(Integer, ForeignKey('persons.id'), nullable=True, index=True)
    zone_id = Column(Integer, ForeignKey('zones.id'), nullable=True)
    video_path = Column(String(512), nullable=True)
    snapshot_path = Column(String(512), nullable=True)
    risk_score = Column(Integer, default=0)
    acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_by = Column(String(255), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    false_positive = Column(Boolean, default=False)
    event_metadata = Column(JSON, default=dict)  # Additional event-specific data

    # Relationships
    person = relationship("Person", back_populates="events")
    zone = relationship("Zone", back_populates="events")
    alerts = relationship("Alert", back_populates="event", cascade="all, delete-orphan")

    # Index for efficient queries
    __table_args__ = (
        Index('idx_severity_time', 'severity', 'timestamp'),
        Index('idx_type_time', 'event_type', 'timestamp'),
    )

    def __repr__(self):
        return f"<Event(id={self.id}, type={self.event_type.value}, severity={self.severity.value})>"


class Alert(Base):
    """
    Alert model for storing alert notifications.
    """
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False, index=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    recipient = Column(String(255), nullable=False)
    sent_at = Column(DateTime, nullable=True)
    status = Column(Enum(AlertStatus), default=AlertStatus.PENDING, nullable=False)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="alerts")

    def __repr__(self):
        return f"<Alert(id={self.id}, type={self.alert_type.value}, status={self.status.value})>"


class Zone(Base):
    """
    Zone model for storing monitored areas and their configurations.
    """
    __tablename__ = 'zones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    zone_type = Column(Enum(ZoneType), nullable=False)
    coordinates = Column(JSON, nullable=False)  # Polygon coordinates [[x1,y1], [x2,y2], ...]
    rules = Column(JSON, default=dict)  # Zone-specific rules configuration
    active = Column(Boolean, default=True, index=True)
    color = Column(String(7), default="#FF0000")  # Hex color for visualization
    loiter_threshold = Column(Integer, default=30)  # seconds
    occupancy_limit = Column(Integer, nullable=True)
    time_based = Column(Boolean, default=False)
    active_start_time = Column(String(5), nullable=True)  # HH:MM format
    active_end_time = Column(String(5), nullable=True)  # HH:MM format
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    events = relationship("Event", back_populates="zone")

    def __repr__(self):
        return f"<Zone(id={self.id}, name='{self.name}', type={self.zone_type.value})>"


class Anomaly(Base):
    """
    Anomaly model for storing detected anomalies.
    """
    __tablename__ = 'anomalies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    anomaly_type = Column(String(100), nullable=False)
    anomaly_score = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    track_id = Column(Integer, nullable=True)
    is_false_positive = Column(Boolean, default=False)
    anomaly_metadata = Column(JSON, default=dict)

    def __repr__(self):
        return f"<Anomaly(id={self.id}, type='{self.anomaly_type}', score={self.anomaly_score:.2f})>"


class SystemLog(Base):
    """
    System log model for storing application logs in database.
    """
    __tablename__ = 'system_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    log_level = Column(Enum(LogLevel), nullable=False, index=True)
    module = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    exception_traceback = Column(Text, nullable=True)

    # Index for efficient queries
    __table_args__ = (
        Index('idx_level_time', 'log_level', 'timestamp'),
    )

    def __repr__(self):
        return f"<SystemLog(id={self.id}, level={self.log_level.value}, module='{self.module}')>"


class Recording(Base):
    """
    Recording model for storing video recording metadata.
    """
    __tablename__ = 'recordings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, nullable=False, index=True)
    file_path = Column(String(512), nullable=False, unique=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    file_size = Column(Integer, nullable=True)  # bytes
    resolution_width = Column(Integer, nullable=True)
    resolution_height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    codec = Column(String(50), nullable=True)
    is_event_triggered = Column(Boolean, default=False)
    event_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Index for efficient queries
    __table_args__ = (
        Index('idx_camera_start_time', 'camera_id', 'start_time'),
    )

    def __repr__(self):
        return f"<Recording(id={self.id}, camera={self.camera_id}, duration={self.duration}s)>"


class User(Base):
    """
    User model for authentication and access control.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="viewer")  # admin, operator, viewer
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class PeopleCount(Base):
    """
    People counting model for tracking occupancy over time.
    """
    __tablename__ = 'people_counts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, nullable=False, index=True)
    zone_id = Column(Integer, ForeignKey('zones.id'), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    count = Column(Integer, nullable=False)
    entries = Column(Integer, default=0)
    exits = Column(Integer, default=0)

    # Index for efficient queries
    __table_args__ = (
        Index('idx_camera_zone_time', 'camera_id', 'zone_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<PeopleCount(id={self.id}, camera={self.camera_id}, count={self.count})>"
