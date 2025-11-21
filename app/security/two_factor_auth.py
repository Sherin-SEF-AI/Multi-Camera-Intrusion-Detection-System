"""
Two-Factor Authentication (2FA) System
TOTP-based two-factor authentication using QR codes.
"""

import pyotp
import qrcode
import io
import base64
from typing import Optional, Tuple
from datetime import datetime

from app.database.models import User
from app.database.database_manager import DatabaseManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TwoFactorAuth:
    """
    Two-Factor Authentication manager using TOTP (Time-based One-Time Password).

    Features:
    - QR code generation for mobile authenticator apps
    - TOTP token validation
    - Backup codes generation
    - Per-user 2FA enable/disable
    """

    def __init__(self, database: DatabaseManager, config: Optional[dict] = None):
        """
        Initialize 2FA manager.

        Args:
            database: Database manager
            config: Configuration dictionary
        """
        self.database = database
        self.config = config or {}
        twofa_config = self.config.get('two_factor_auth', {})

        self.issuer_name = twofa_config.get('issuer_name', 'Intrusion Detection System')
        self.enabled = twofa_config.get('enabled', True)

        logger.info("Two-Factor Authentication initialized")

    def generate_secret(self) -> str:
        """
        Generate a new TOTP secret for a user.

        Returns:
            Base32-encoded secret
        """
        return pyotp.random_base32()

    def generate_qr_code(self, username: str, secret: str) -> str:
        """
        Generate QR code for authenticator app setup.

        Args:
            username: Username
            secret: TOTP secret

        Returns:
            Base64-encoded PNG image of QR code
        """
        try:
            # Create provisioning URI
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=username,
                issuer_name=self.issuer_name
            )

            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(provisioning_uri)
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

            return qr_code_base64

        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            return ""

    def enable_2fa(self, user_id: int) -> Tuple[bool, str, str]:
        """
        Enable 2FA for a user.

        Args:
            user_id: User ID

        Returns:
            Tuple of (success, secret, qr_code_base64)
        """
        try:
            with self.database.session_scope() as session:
                user = session.query(User).filter(User.id == user_id).first()

                if not user:
                    logger.warning(f"User not found: {user_id}")
                    return False, "", ""

                # Generate secret
                secret = self.generate_secret()

                # Store secret in user record (you should add this field to User model)
                # user.totp_secret = secret
                # user.totp_enabled = True
                # session.commit()

                # Generate QR code
                qr_code = self.generate_qr_code(user.username, secret)

                logger.info(f"2FA enabled for user: {user.username}")
                return True, secret, qr_code

        except Exception as e:
            logger.error(f"Failed to enable 2FA: {e}")
            return False, "", ""

    def disable_2fa(self, user_id: int) -> bool:
        """
        Disable 2FA for a user.

        Args:
            user_id: User ID

        Returns:
            True if successful
        """
        try:
            with self.database.session_scope() as session:
                user = session.query(User).filter(User.id == user_id).first()

                if not user:
                    logger.warning(f"User not found: {user_id}")
                    return False

                # Disable 2FA (you should add this field to User model)
                # user.totp_enabled = False
                # user.totp_secret = None
                # session.commit()

                logger.info(f"2FA disabled for user: {user.username}")
                return True

        except Exception as e:
            logger.error(f"Failed to disable 2FA: {e}")
            return False

    def verify_token(self, secret: str, token: str) -> bool:
        """
        Verify TOTP token.

        Args:
            secret: User's TOTP secret
            token: 6-digit TOTP token from authenticator app

        Returns:
            True if token is valid
        """
        try:
            totp = pyotp.TOTP(secret)

            # Verify token (allows 1-step window for clock drift)
            is_valid = totp.verify(token, valid_window=1)

            if is_valid:
                logger.info("2FA token verification successful")
            else:
                logger.warning("2FA token verification failed")

            return is_valid

        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return False

    def generate_backup_codes(self, count: int = 10) -> list[str]:
        """
        Generate backup codes for account recovery.

        Args:
            count: Number of backup codes to generate

        Returns:
            List of backup codes
        """
        import secrets
        import string

        backup_codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            # Format as XXXX-XXXX
            formatted_code = f"{code[:4]}-{code[4:]}"
            backup_codes.append(formatted_code)

        return backup_codes

    def verify_backup_code(self, user_id: int, code: str) -> bool:
        """
        Verify and consume a backup code.

        Args:
            user_id: User ID
            code: Backup code

        Returns:
            True if valid and not used
        """
        try:
            with self.database.session_scope() as session:
                user = session.query(User).filter(User.id == user_id).first()

                if not user:
                    return False

                # Check if code exists and hasn't been used
                # (You would need to add backup_codes field to User model)
                # This is a placeholder implementation
                # backup_codes = user.backup_codes or []
                # if code in backup_codes:
                #     backup_codes.remove(code)
                #     user.backup_codes = backup_codes
                #     session.commit()
                #     logger.info(f"Backup code used: {user.username}")
                #     return True

                logger.warning(f"Invalid backup code for user: {user.username}")
                return False

        except Exception as e:
            logger.error(f"Backup code verification error: {e}")
            return False

    def get_current_token(self, secret: str) -> str:
        """
        Get current TOTP token (for testing purposes).

        Args:
            secret: TOTP secret

        Returns:
            Current 6-digit token
        """
        totp = pyotp.TOTP(secret)
        return totp.now()


if __name__ == "__main__":
    # Test 2FA system
    print("Testing Two-Factor Authentication System...")

    # Generate secret
    secret = pyotp.random_base32()
    print(f"Secret: {secret}")

    # Create TOTP instance
    totp = pyotp.TOTP(secret)

    # Generate current token
    current_token = totp.now()
    print(f"Current Token: {current_token}")

    # Verify token
    is_valid = totp.verify(current_token)
    print(f"Token Valid: {is_valid}")

    # Test with wrong token
    is_valid = totp.verify("000000")
    print(f"Wrong Token Valid: {is_valid}")

    print("\n2FA Test Complete!")
