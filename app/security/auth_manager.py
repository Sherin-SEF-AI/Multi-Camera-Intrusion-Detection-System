"""
Authentication and Authorization Manager
User authentication, session management, and role-based access control (RBAC).
"""

import hashlib
import secrets
import time
from typing import Optional, Dict, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

from app.database.models import User, UserRole
from app.database.database_manager import DatabaseManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Session:
    """User session."""
    session_id: str
    user_id: int
    username: str
    role: UserRole
    created_at: datetime
    last_activity: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class Permission(Enum):
    """System permissions."""
    # View permissions
    VIEW_LIVE_FEED = "view_live_feed"
    VIEW_RECORDINGS = "view_recordings"
    VIEW_ANALYTICS = "view_analytics"
    VIEW_EVENTS = "view_events"
    VIEW_PERSONS = "view_persons"
    VIEW_ZONES = "view_zones"
    VIEW_SETTINGS = "view_settings"
    VIEW_USERS = "view_users"
    VIEW_LOGS = "view_logs"

    # Modify permissions
    MODIFY_PERSONS = "modify_persons"
    MODIFY_ZONES = "modify_zones"
    MODIFY_SETTINGS = "modify_settings"
    MODIFY_USERS = "modify_users"

    # Action permissions
    ACKNOWLEDGE_EVENTS = "acknowledge_events"
    TRIGGER_ALERTS = "trigger_alerts"
    EXPORT_DATA = "export_data"
    DELETE_RECORDINGS = "delete_recordings"

    # System permissions
    MANAGE_SYSTEM = "manage_system"
    ACCESS_API = "access_api"


# Role-Permission mapping
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: {
        # Admins have all permissions
        Permission.VIEW_LIVE_FEED,
        Permission.VIEW_RECORDINGS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_EVENTS,
        Permission.VIEW_PERSONS,
        Permission.VIEW_ZONES,
        Permission.VIEW_SETTINGS,
        Permission.VIEW_USERS,
        Permission.VIEW_LOGS,
        Permission.MODIFY_PERSONS,
        Permission.MODIFY_ZONES,
        Permission.MODIFY_SETTINGS,
        Permission.MODIFY_USERS,
        Permission.ACKNOWLEDGE_EVENTS,
        Permission.TRIGGER_ALERTS,
        Permission.EXPORT_DATA,
        Permission.DELETE_RECORDINGS,
        Permission.MANAGE_SYSTEM,
        Permission.ACCESS_API,
    },
    UserRole.OPERATOR: {
        # Operators can view and manage daily operations
        Permission.VIEW_LIVE_FEED,
        Permission.VIEW_RECORDINGS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_EVENTS,
        Permission.VIEW_PERSONS,
        Permission.VIEW_ZONES,
        Permission.MODIFY_PERSONS,
        Permission.MODIFY_ZONES,
        Permission.ACKNOWLEDGE_EVENTS,
        Permission.TRIGGER_ALERTS,
        Permission.EXPORT_DATA,
    },
    UserRole.VIEWER: {
        # Viewers can only view, no modifications
        Permission.VIEW_LIVE_FEED,
        Permission.VIEW_RECORDINGS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_EVENTS,
        Permission.VIEW_PERSONS,
        Permission.VIEW_ZONES,
    },
}


class AuthenticationManager:
    """
    Manages user authentication and authorization.

    Features:
    - Password hashing (bcrypt)
    - Session management
    - Role-based access control (RBAC)
    - Session timeout
    - Login attempt limiting
    - Audit logging
    """

    def __init__(self, database: DatabaseManager, config: Optional[dict] = None):
        """
        Initialize authentication manager.

        Args:
            database: Database manager
            config: Configuration dictionary
        """
        self.database = database
        self.config = config or {}
        auth_config = self.config.get('authentication', {})

        # Configuration
        self.session_timeout = auth_config.get('session_timeout', 3600)  # 1 hour
        self.max_login_attempts = auth_config.get('max_login_attempts', 5)
        self.lockout_duration = auth_config.get('lockout_duration', 900)  # 15 minutes
        self.password_min_length = auth_config.get('password_min_length', 8)
        self.require_strong_password = auth_config.get('require_strong_password', True)

        # Active sessions {session_id: Session}
        self.sessions: Dict[str, Session] = {}

        # Login attempts {username: (count, last_attempt_time)}
        self.login_attempts: Dict[str, tuple[int, float]] = {}

        # Locked accounts {username: unlock_time}
        self.locked_accounts: Dict[str, float] = {}

        # Check bcrypt availability
        if not BCRYPT_AVAILABLE:
            logger.warning("bcrypt not available. Using fallback (less secure).")
            logger.warning("Install with: pip install bcrypt")

        logger.info("Authentication Manager initialized")

    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        if BCRYPT_AVAILABLE:
            # Use bcrypt (recommended)
            salt = bcrypt.gensalt(rounds=12)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        else:
            # Fallback to SHA-256 with salt (less secure)
            salt = secrets.token_hex(16)
            hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
            return f"{salt}${hashed.hex()}"

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password
            hashed_password: Hashed password

        Returns:
            True if password matches
        """
        try:
            if BCRYPT_AVAILABLE and not '$' in hashed_password[10:]:
                # bcrypt format
                return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
            else:
                # Fallback format
                salt, hash_hex = hashed_password.split('$')
                computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
                return computed_hash.hex() == hash_hex
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def validate_password_strength(self, password: str) -> tuple[bool, str]:
        """
        Validate password strength.

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < self.password_min_length:
            return False, f"Password must be at least {self.password_min_length} characters"

        if not self.require_strong_password:
            return True, ""

        # Check for uppercase
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        # Check for lowercase
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        # Check for digit
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"

        # Check for special character
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "Password must contain at least one special character"

        return True, ""

    def create_user(
        self,
        username: str,
        password: str,
        email: str,
        full_name: str,
        role: UserRole = UserRole.VIEWER
    ) -> Optional[User]:
        """
        Create new user account.

        Args:
            username: Username
            password: Password
            email: Email address
            full_name: Full name
            role: User role

        Returns:
            Created User object or None
        """
        try:
            # Validate password
            is_valid, error_msg = self.validate_password_strength(password)
            if not is_valid:
                logger.warning(f"Password validation failed: {error_msg}")
                return None

            # Check if username exists
            with self.database.session_scope() as session:
                existing_user = session.query(User).filter(User.username == username).first()
                if existing_user:
                    logger.warning(f"Username already exists: {username}")
                    return None

                # Hash password
                password_hash = self.hash_password(password)

                # Create user
                user = User(
                    username=username,
                    password_hash=password_hash,
                    email=email,
                    full_name=full_name,
                    role=role,
                    is_active=True
                )

                session.add(user)
                session.commit()

                logger.info(f"User created: {username} ({role.value})")
                return user

        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None

    def authenticate(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[str]:
        """
        Authenticate user and create session.

        Args:
            username: Username
            password: Password
            ip_address: Client IP address
            user_agent: User agent string

        Returns:
            Session ID if successful, None otherwise
        """
        try:
            # Check if account is locked
            if username in self.locked_accounts:
                unlock_time = self.locked_accounts[username]
                if time.time() < unlock_time:
                    remaining = int(unlock_time - time.time())
                    logger.warning(f"Account locked: {username} ({remaining}s remaining)")
                    return None
                else:
                    # Unlock account
                    del self.locked_accounts[username]
                    self.login_attempts.pop(username, None)

            # Get user from database
            with self.database.session_scope() as session:
                user = session.query(User).filter(User.username == username).first()

                if not user or not user.is_active:
                    self._record_failed_login(username)
                    logger.warning(f"Authentication failed: Invalid username {username}")
                    return None

                # Verify password
                if not self.verify_password(password, user.password_hash):
                    self._record_failed_login(username)
                    logger.warning(f"Authentication failed: Invalid password for {username}")
                    return None

                # Update last login
                user.last_login = datetime.now()
                session.commit()

                # Clear login attempts
                self.login_attempts.pop(username, None)

                # Create session
                session_id = self._create_session(
                    user.id,
                    username,
                    user.role,
                    ip_address,
                    user_agent
                )

                logger.info(f"User authenticated: {username} (role: {user.role.value})")
                return session_id

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    def _record_failed_login(self, username: str):
        """Record failed login attempt."""
        current_time = time.time()

        if username in self.login_attempts:
            count, _ = self.login_attempts[username]
            count += 1
        else:
            count = 1

        self.login_attempts[username] = (count, current_time)

        # Lock account if too many attempts
        if count >= self.max_login_attempts:
            unlock_time = current_time + self.lockout_duration
            self.locked_accounts[username] = unlock_time
            logger.warning(f"Account locked due to failed attempts: {username}")

    def _create_session(
        self,
        user_id: int,
        username: str,
        role: UserRole,
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> str:
        """Create new session."""
        session_id = secrets.token_urlsafe(32)

        session = Session(
            session_id=session_id,
            user_id=user_id,
            username=username,
            role=role,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            ip_address=ip_address,
            user_agent=user_agent
        )

        self.sessions[session_id] = session

        return session_id

    def validate_session(self, session_id: str) -> Optional[Session]:
        """
        Validate session and update activity.

        Args:
            session_id: Session ID

        Returns:
            Session object if valid, None otherwise
        """
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # Check timeout
        inactive_duration = (datetime.now() - session.last_activity).total_seconds()
        if inactive_duration > self.session_timeout:
            logger.info(f"Session expired: {session.username}")
            self.logout(session_id)
            return None

        # Update activity
        session.last_activity = datetime.now()

        return session

    def logout(self, session_id: str) -> bool:
        """
        Logout user and destroy session.

        Args:
            session_id: Session ID

        Returns:
            True if successful
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            logger.info(f"User logged out: {session.username}")
            del self.sessions[session_id]
            return True

        return False

    def has_permission(self, session_id: str, permission: Permission) -> bool:
        """
        Check if user has permission.

        Args:
            session_id: Session ID
            permission: Required permission

        Returns:
            True if user has permission
        """
        session = self.validate_session(session_id)
        if not session:
            return False

        return permission in ROLE_PERMISSIONS.get(session.role, set())

    def require_permission(self, session_id: str, permission: Permission) -> bool:
        """
        Require permission (raises exception if not authorized).

        Args:
            session_id: Session ID
            permission: Required permission

        Returns:
            True if authorized

        Raises:
            PermissionError if not authorized
        """
        if not self.has_permission(session_id, permission):
            session = self.validate_session(session_id)
            username = session.username if session else "unknown"
            logger.warning(f"Permission denied: {username} -> {permission.value}")
            raise PermissionError(f"Insufficient permissions: {permission.value}")

        return True

    def get_active_sessions(self) -> List[Session]:
        """
        Get all active sessions.

        Returns:
            List of active sessions
        """
        # Clean expired sessions first
        self._cleanup_expired_sessions()

        return list(self.sessions.values())

    def _cleanup_expired_sessions(self):
        """Remove expired sessions."""
        current_time = datetime.now()
        expired = []

        for session_id, session in self.sessions.items():
            inactive_duration = (current_time - session.last_activity).total_seconds()
            if inactive_duration > self.session_timeout:
                expired.append(session_id)

        for session_id in expired:
            username = self.sessions[session_id].username
            logger.info(f"Session expired and removed: {username}")
            del self.sessions[session_id]

    def change_password(
        self,
        session_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password.

        Args:
            session_id: Session ID
            old_password: Current password
            new_password: New password

        Returns:
            True if successful
        """
        session = self.validate_session(session_id)
        if not session:
            return False

        try:
            # Validate new password
            is_valid, error_msg = self.validate_password_strength(new_password)
            if not is_valid:
                logger.warning(f"Password validation failed: {error_msg}")
                return False

            with self.database.session_scope() as db_session:
                user = db_session.query(User).filter(User.id == session.user_id).first()

                if not user:
                    return False

                # Verify old password
                if not self.verify_password(old_password, user.password_hash):
                    logger.warning(f"Password change failed: Invalid old password for {user.username}")
                    return False

                # Update password
                user.password_hash = self.hash_password(new_password)
                db_session.commit()

                logger.info(f"Password changed: {user.username}")
                return True

        except Exception as e:
            logger.error(f"Password change error: {e}")
            return False

    def get_statistics(self) -> Dict:
        """
        Get authentication statistics.

        Returns:
            Statistics dictionary
        """
        return {
            'active_sessions': len(self.sessions),
            'locked_accounts': len(self.locked_accounts),
            'failed_login_attempts': len(self.login_attempts),
            'session_timeout': self.session_timeout,
        }


if __name__ == "__main__":
    # Test authentication manager
    from app.database.database_manager import DatabaseManager

    config = {
        'database': {
            'url': 'sqlite:///test_auth.db'
        },
        'authentication': {
            'session_timeout': 3600,
            'max_login_attempts': 5,
            'password_min_length': 8,
            'require_strong_password': True
        }
    }

    # Initialize database
    db = DatabaseManager(config)
    db.initialize()

    # Initialize auth manager
    auth = AuthenticationManager(db, config)

    # Create test user
    print("Creating admin user...")
    user = auth.create_user(
        username="admin",
        password="Admin123!",
        email="admin@example.com",
        full_name="System Administrator",
        role=UserRole.ADMIN
    )

    if user:
        print(f"User created: {user.username}")

        # Test authentication
        print("\nAuthenticating...")
        session_id = auth.authenticate("admin", "Admin123!")

        if session_id:
            print(f"Authenticated successfully. Session ID: {session_id}")

            # Test permissions
            print("\nTesting permissions...")
            has_perm = auth.has_permission(session_id, Permission.MANAGE_SYSTEM)
            print(f"Has MANAGE_SYSTEM permission: {has_perm}")

            has_perm = auth.has_permission(session_id, Permission.VIEW_LIVE_FEED)
            print(f"Has VIEW_LIVE_FEED permission: {has_perm}")

            # Test session validation
            print("\nValidating session...")
            session = auth.validate_session(session_id)
            if session:
                print(f"Session valid: {session.username} ({session.role.value})")

            # Logout
            print("\nLogging out...")
            auth.logout(session_id)

        # Test failed login
        print("\nTesting failed login...")
        bad_session = auth.authenticate("admin", "wrong_password")
        print(f"Failed login result: {bad_session}")

    # Statistics
    stats = auth.get_statistics()
    print(f"\nStatistics: {stats}")

    print("\nTest complete")
