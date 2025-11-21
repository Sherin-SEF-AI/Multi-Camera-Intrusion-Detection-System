"""
Audit Logging System
Comprehensive audit trail for security compliance and forensic analysis.
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict

from app.database.models import SystemLog, LogLevel
from app.database.database_manager import DatabaseManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    SESSION_EXPIRED = "session_expired"

    # Authorization events
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_CHANGED = "role_changed"

    # User management
    USER_CREATED = "user_created"
    USER_MODIFIED = "user_modified"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"

    # Person database
    PERSON_ADDED = "person_added"
    PERSON_MODIFIED = "person_modified"
    PERSON_DELETED = "person_deleted"
    PERSON_IDENTIFIED = "person_identified"

    # Zone management
    ZONE_CREATED = "zone_created"
    ZONE_MODIFIED = "zone_modified"
    ZONE_DELETED = "zone_deleted"
    ZONE_VIOLATION = "zone_violation"

    # Event management
    EVENT_CREATED = "event_created"
    EVENT_ACKNOWLEDGED = "event_acknowledged"
    EVENT_RESOLVED = "event_resolved"
    EVENT_DELETED = "event_deleted"

    # Alert management
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_SENT = "alert_sent"
    ALERT_FAILED = "alert_failed"

    # System configuration
    CONFIG_CHANGED = "config_changed"
    SETTINGS_MODIFIED = "settings_modified"
    CAMERA_ADDED = "camera_added"
    CAMERA_REMOVED = "camera_removed"
    CAMERA_DISCONNECTED = "camera_disconnected"

    # Data operations
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"
    DATABASE_BACKUP = "database_backup"
    DATABASE_RESTORED = "database_restored"

    # Recording operations
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    RECORDING_DELETED = "recording_deleted"

    # Security events
    INTRUSION_DETECTED = "intrusion_detected"
    ANOMALY_DETECTED = "anomaly_detected"
    THREAT_ASSESSED = "threat_assessed"
    BEHAVIORAL_ALERT = "behavioral_alert"

    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event."""
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None


class AuditLogger:
    """
    Comprehensive audit logging system.

    Features:
    - Detailed audit trail
    - Database persistence
    - Search and filtering
    - Compliance reporting
    - Forensic analysis support
    - Event correlation
    """

    def __init__(self, database: DatabaseManager, config: Optional[dict] = None):
        """
        Initialize audit logger.

        Args:
            database: Database manager
            config: Configuration dictionary
        """
        self.database = database
        self.config = config or {}
        audit_config = self.config.get('audit_logging', {})

        # Configuration
        self.enabled = audit_config.get('enabled', True)
        self.log_to_database = audit_config.get('log_to_database', True)
        self.log_to_file = audit_config.get('log_to_file', True)
        self.retention_days = audit_config.get('retention_days', 90)

        # Statistics
        self.total_events = 0
        self.events_by_type: Dict[str, int] = {}

        logger.info("Audit Logger initialized")

    def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        Log audit event.

        Args:
            event_type: Type of event
            severity: Event severity
            user_id: User ID
            username: Username
            session_id: Session ID
            ip_address: IP address
            resource_type: Resource type
            resource_id: Resource ID
            action: Action performed
            details: Additional details
            success: Whether action succeeded
            error_message: Error message if failed
        """
        if not self.enabled:
            return

        try:
            event = AuditEvent(
                event_type=event_type,
                severity=severity,
                timestamp=datetime.now(),
                user_id=user_id,
                username=username,
                session_id=session_id,
                ip_address=ip_address,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                details=details or {},
                success=success,
                error_message=error_message
            )

            # Log to database
            if self.log_to_database:
                self._log_to_database(event)

            # Log to file
            if self.log_to_file:
                self._log_to_file(event)

            # Update statistics
            self.total_events += 1
            event_type_str = event_type.value
            self.events_by_type[event_type_str] = self.events_by_type.get(event_type_str, 0) + 1

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

    def _log_to_database(self, event: AuditEvent):
        """Log event to database."""
        try:
            # Convert severity to LogLevel
            level_map = {
                AuditSeverity.INFO: LogLevel.INFO,
                AuditSeverity.WARNING: LogLevel.WARNING,
                AuditSeverity.ERROR: LogLevel.ERROR,
                AuditSeverity.CRITICAL: LogLevel.CRITICAL
            }

            log_level = level_map.get(event.severity, LogLevel.INFO)

            # Create log entry
            log_entry = SystemLog(
                level=log_level,
                module="audit",
                message=f"{event.event_type.value}: {event.action or 'N/A'}",
                details={
                    'event_type': event.event_type.value,
                    'user_id': event.user_id,
                    'username': event.username,
                    'session_id': event.session_id,
                    'ip_address': event.ip_address,
                    'resource_type': event.resource_type,
                    'resource_id': event.resource_id,
                    'action': event.action,
                    'success': event.success,
                    'error_message': event.error_message,
                    **(event.details or {})
                },
                user_id=event.user_id
            )

            self.database.add(log_entry)

        except Exception as e:
            logger.error(f"Failed to log to database: {e}")

    def _log_to_file(self, event: AuditEvent):
        """Log event to file (via logger)."""
        try:
            # Format message
            message = self._format_audit_message(event)

            # Log based on severity
            if event.severity == AuditSeverity.CRITICAL:
                logger.critical(message)
            elif event.severity == AuditSeverity.ERROR:
                logger.error(message)
            elif event.severity == AuditSeverity.WARNING:
                logger.warning(message)
            else:
                logger.info(message)

        except Exception as e:
            logger.error(f"Failed to log to file: {e}")

    def _format_audit_message(self, event: AuditEvent) -> str:
        """
        Format audit event as string.

        Args:
            event: Audit event

        Returns:
            Formatted message
        """
        parts = [f"AUDIT [{event.event_type.value}]"]

        if event.username:
            parts.append(f"User: {event.username}")

        if event.action:
            parts.append(f"Action: {event.action}")

        if event.resource_type and event.resource_id:
            parts.append(f"Resource: {event.resource_type}#{event.resource_id}")

        if event.ip_address:
            parts.append(f"IP: {event.ip_address}")

        status = "SUCCESS" if event.success else "FAILED"
        parts.append(f"Status: {status}")

        if event.error_message:
            parts.append(f"Error: {event.error_message}")

        if event.details:
            parts.append(f"Details: {json.dumps(event.details)}")

        return " | ".join(parts)

    # Convenience methods for common events

    def log_login(self, username: str, success: bool, ip_address: Optional[str] = None, error: Optional[str] = None):
        """Log login event."""
        self.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILURE,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            username=username,
            ip_address=ip_address,
            action="login",
            success=success,
            error_message=error
        )

    def log_logout(self, username: str, session_id: str):
        """Log logout event."""
        self.log_event(
            event_type=AuditEventType.LOGOUT,
            severity=AuditSeverity.INFO,
            username=username,
            session_id=session_id,
            action="logout"
        )

    def log_permission_check(self, username: str, permission: str, granted: bool):
        """Log permission check."""
        self.log_event(
            event_type=AuditEventType.PERMISSION_GRANTED if granted else AuditEventType.PERMISSION_DENIED,
            severity=AuditSeverity.INFO if granted else AuditSeverity.WARNING,
            username=username,
            action=f"check_permission:{permission}",
            success=granted
        )

    def log_data_modification(
        self,
        username: str,
        resource_type: str,
        resource_id: int,
        action: str,
        details: Optional[Dict] = None
    ):
        """Log data modification event."""
        # Map action to event type
        event_type_map = {
            'create': f"{resource_type.upper()}_CREATED",
            'modify': f"{resource_type.upper()}_MODIFIED",
            'delete': f"{resource_type.upper()}_DELETED"
        }

        event_type_str = event_type_map.get(action, "DATA_MODIFIED")

        try:
            event_type = AuditEventType(event_type_str.lower())
        except ValueError:
            event_type = AuditEventType.SYSTEM_WARNING

        self.log_event(
            event_type=event_type,
            severity=AuditSeverity.INFO,
            username=username,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details
        )

    def log_security_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        details: Dict[str, Any]
    ):
        """Log security event."""
        self.log_event(
            event_type=event_type,
            severity=severity,
            action="security_event",
            details=details
        )

    def log_system_event(
        self,
        event_type: AuditEventType,
        message: str,
        severity: AuditSeverity = AuditSeverity.INFO
    ):
        """Log system event."""
        self.log_event(
            event_type=event_type,
            severity=severity,
            action="system_event",
            details={'message': message}
        )

    def search_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
        username: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        success: Optional[bool] = None,
        limit: int = 100
    ) -> List[SystemLog]:
        """
        Search audit events.

        Args:
            start_date: Start date filter
            end_date: End date filter
            event_type: Event type filter
            username: Username filter
            resource_type: Resource type filter
            severity: Severity filter
            success: Success filter
            limit: Maximum results

        Returns:
            List of matching log entries
        """
        try:
            with self.database.session_scope() as session:
                query = session.query(SystemLog).filter(SystemLog.module == "audit")

                # Apply filters
                if start_date:
                    query = query.filter(SystemLog.created_at >= start_date)

                if end_date:
                    query = query.filter(SystemLog.created_at <= end_date)

                if severity:
                    level_map = {
                        AuditSeverity.INFO: LogLevel.INFO,
                        AuditSeverity.WARNING: LogLevel.WARNING,
                        AuditSeverity.ERROR: LogLevel.ERROR,
                        AuditSeverity.CRITICAL: LogLevel.CRITICAL
                    }
                    query = query.filter(SystemLog.level == level_map[severity])

                if username:
                    # Search in details JSON
                    query = query.filter(SystemLog.details['username'].astext == username)

                # Order by timestamp descending
                query = query.order_by(SystemLog.created_at.desc())

                # Limit results
                query = query.limit(limit)

                return query.all()

        except Exception as e:
            logger.error(f"Failed to search events: {e}")
            return []

    def cleanup_old_events(self):
        """Remove old audit events based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)

            with self.database.session_scope() as session:
                deleted = session.query(SystemLog).filter(
                    SystemLog.module == "audit",
                    SystemLog.created_at < cutoff_date
                ).delete()

                session.commit()

                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old audit events")

        except Exception as e:
            logger.error(f"Failed to cleanup old events: {e}")

    def get_statistics(self, days: int = 30) -> Dict:
        """
        Get audit statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Statistics dictionary
        """
        try:
            start_date = datetime.now() - timedelta(days=days)

            with self.database.session_scope() as session:
                total_events = session.query(SystemLog).filter(
                    SystemLog.module == "audit",
                    SystemLog.created_at >= start_date
                ).count()

                critical_events = session.query(SystemLog).filter(
                    SystemLog.module == "audit",
                    SystemLog.level == LogLevel.CRITICAL,
                    SystemLog.created_at >= start_date
                ).count()

                error_events = session.query(SystemLog).filter(
                    SystemLog.module == "audit",
                    SystemLog.level == LogLevel.ERROR,
                    SystemLog.created_at >= start_date
                ).count()

                warning_events = session.query(SystemLog).filter(
                    SystemLog.module == "audit",
                    SystemLog.level == LogLevel.WARNING,
                    SystemLog.created_at >= start_date
                ).count()

                return {
                    'total_events': total_events,
                    'critical_events': critical_events,
                    'error_events': error_events,
                    'warning_events': warning_events,
                    'period_days': days,
                    'retention_days': self.retention_days
                }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}


if __name__ == "__main__":
    # Test audit logger
    from app.database.database_manager import DatabaseManager

    config = {
        'database': {
            'url': 'sqlite:///test_audit.db'
        },
        'audit_logging': {
            'enabled': True,
            'log_to_database': True,
            'log_to_file': True,
            'retention_days': 90
        }
    }

    # Initialize database
    db = DatabaseManager(config)
    db.initialize()

    # Initialize audit logger
    audit = AuditLogger(db, config)

    # Test logging events
    print("Logging test events...")

    audit.log_login("admin", success=True, ip_address="192.168.1.100")
    audit.log_login("hacker", success=False, ip_address="10.0.0.50", error="Invalid password")
    audit.log_permission_check("admin", "MANAGE_SYSTEM", granted=True)
    audit.log_permission_check("viewer", "MODIFY_USERS", granted=False)

    audit.log_data_modification(
        username="admin",
        resource_type="person",
        resource_id=1,
        action="create",
        details={'name': 'John Doe'}
    )

    audit.log_security_event(
        event_type=AuditEventType.INTRUSION_DETECTED,
        severity=AuditSeverity.CRITICAL,
        details={'camera_id': 0, 'zone': 'Restricted Area'}
    )

    audit.log_system_event(
        event_type=AuditEventType.SYSTEM_STARTED,
        message="System initialized successfully"
    )

    # Search events
    print("\nSearching events...")
    events = audit.search_events(
        start_date=datetime.now() - timedelta(hours=1),
        limit=10
    )

    print(f"Found {len(events)} events")
    for event in events:
        print(f"  - {event.created_at}: {event.message}")

    # Statistics
    stats = audit.get_statistics(days=1)
    print(f"\nStatistics: {stats}")

    print("\nTest complete")
