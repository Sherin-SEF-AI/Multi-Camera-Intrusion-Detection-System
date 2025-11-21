"""
Alert Manager
Multi-channel alert delivery system (Email, SMS, Webhook, System).
"""

import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import threading
from queue import Queue
import time

from app.utils.logger import get_logger
from app.database.models import Alert, Event, AlertType, AlertStatus

logger = get_logger(__name__)


class EmailAlertSender:
    """
    Email alert sender using SMTP.
    """

    def __init__(self, config: dict):
        """
        Initialize email sender.

        Args:
            config: Email configuration
        """
        self.config = config
        self.smtp_server = config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.use_tls = config.get('use_tls', True)
        self.sender_email = config.get('sender_email', '')
        self.sender_password = config.get('sender_password', '')
        self.recipients = config.get('recipients', [])

    def send(
        self,
        subject: str,
        body: str,
        recipients: Optional[List[str]] = None,
        snapshot_path: Optional[str] = None
    ) -> bool:
        """
        Send email alert.

        Args:
            subject: Email subject
            body: Email body (HTML supported)
            recipients: List of recipient emails (overrides default)
            snapshot_path: Optional path to image attachment

        Returns:
            True if sent successfully
        """
        try:
            if not self.sender_email or not self.sender_password:
                logger.warning("Email credentials not configured")
                return False

            # Use provided recipients or default
            to_emails = recipients or self.recipients

            if not to_emails:
                logger.warning("No email recipients configured")
                return False

            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

            # Add body
            msg.attach(MIMEText(body, 'html'))

            # Attach snapshot if provided
            if snapshot_path and Path(snapshot_path).exists():
                with open(snapshot_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-Disposition', 'attachment', filename=Path(snapshot_path).name)
                    msg.attach(img)

            # Connect and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email sent to {', '.join(to_emails)}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


class SMSAlertSender:
    """
    SMS alert sender using Twilio.
    """

    def __init__(self, config: dict):
        """
        Initialize SMS sender.

        Args:
            config: SMS/Twilio configuration
        """
        self.config = config
        self.account_sid = config.get('account_sid', '')
        self.auth_token = config.get('auth_token', '')
        self.from_number = config.get('from_number', '')
        self.to_numbers = config.get('to_numbers', [])

    def send(self, message: str, to_numbers: Optional[List[str]] = None) -> bool:
        """
        Send SMS alert.

        Args:
            message: SMS message text
            to_numbers: List of phone numbers (overrides default)

        Returns:
            True if sent successfully
        """
        try:
            if not self.account_sid or not self.auth_token:
                logger.warning("Twilio credentials not configured")
                return False

            # Import Twilio (optional dependency)
            try:
                from twilio.rest import Client
            except ImportError:
                logger.error("Twilio not installed. Run: pip install twilio")
                return False

            # Use provided numbers or default
            recipients = to_numbers or self.to_numbers

            if not recipients:
                logger.warning("No SMS recipients configured")
                return False

            # Create Twilio client
            client = Client(self.account_sid, self.auth_token)

            # Send to each recipient
            success = True
            for number in recipients:
                try:
                    message_obj = client.messages.create(
                        body=message,
                        from_=self.from_number,
                        to=number
                    )
                    logger.info(f"SMS sent to {number}: {message_obj.sid}")
                except Exception as e:
                    logger.error(f"Failed to send SMS to {number}: {e}")
                    success = False

            return success

        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False


class WebhookAlertSender:
    """
    Webhook alert sender via HTTP POST.
    """

    def __init__(self, config: dict):
        """
        Initialize webhook sender.

        Args:
            config: Webhook configuration
        """
        self.config = config
        self.url = config.get('url', '')
        self.method = config.get('method', 'POST')
        self.headers = config.get('headers', {})
        self.timeout = config.get('timeout', 10)

    def send(self, payload: Dict[str, Any]) -> bool:
        """
        Send webhook alert.

        Args:
            payload: JSON payload to send

        Returns:
            True if sent successfully
        """
        try:
            if not self.url:
                logger.warning("Webhook URL not configured")
                return False

            # Add timestamp
            payload['timestamp'] = datetime.now().isoformat()

            # Send request
            if self.method.upper() == 'POST':
                response = requests.post(
                    self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout
                )
            elif self.method.upper() == 'PUT':
                response = requests.put(
                    self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout
                )
            else:
                logger.error(f"Unsupported HTTP method: {self.method}")
                return False

            # Check response
            if response.status_code in [200, 201, 202]:
                logger.info(f"Webhook sent successfully: {response.status_code}")
                return True
            else:
                logger.warning(f"Webhook returned {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False


class AlertManager:
    """
    Central alert management system coordinating all alert channels.

    Features:
    - Multi-channel alerts (Email, SMS, Webhook, System)
    - Alert queuing and retry logic
    - Rate limiting to prevent spam
    - Alert history tracking
    - Database integration
    """

    def __init__(self, config: dict, database=None):
        """
        Initialize alert manager.

        Args:
            config: Alert configuration
            database: DatabaseManager instance
        """
        self.config = config.get('alerts', {})
        self.database = database

        # Initialize senders
        self.email_sender = EmailAlertSender(self.config.get('email', {}))
        self.sms_sender = SMSAlertSender(self.config.get('sms', {}))
        self.webhook_sender = WebhookAlertSender(self.config.get('webhook', {}))

        # Alert queue
        self.alert_queue: Queue = Queue()
        self.processing_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Rate limiting
        self.last_alert_time = {}
        self.min_interval = self.config.get('rules', {}).get('min_interval', 60)

        # Start processing
        self._start_processing()

        logger.info("Alert Manager initialized")

    def _start_processing(self):
        """Start alert processing thread."""
        self.stop_event.clear()
        self.processing_thread = threading.Thread(
            target=self._process_alerts,
            name="AlertProcessor",
            daemon=True
        )
        self.processing_thread.start()

    def _process_alerts(self):
        """Process alerts from queue."""
        logger.info("Alert processing thread started")

        while not self.stop_event.is_set():
            try:
                # Get alert from queue (with timeout)
                try:
                    alert_data = self.alert_queue.get(timeout=1.0)
                except:
                    continue

                # Process alert
                self._send_alert(alert_data)

                # Mark as done
                self.alert_queue.task_done()

            except Exception as e:
                logger.error(f"Error processing alert: {e}")

        logger.info("Alert processing thread stopped")

    def _send_alert(self, alert_data: Dict[str, Any]):
        """
        Send alert through configured channels.

        Args:
            alert_data: Alert information dictionary
        """
        event_id = alert_data.get('event_id')
        event_type = alert_data.get('event_type', 'unknown')
        severity = alert_data.get('severity', 'medium')
        description = alert_data.get('description', '')
        camera_id = alert_data.get('camera_id', 0)
        snapshot_path = alert_data.get('snapshot_path')
        risk_score = alert_data.get('risk_score', 0)

        # Check rate limiting
        alert_key = f"{event_type}_{camera_id}"
        current_time = time.time()

        if alert_key in self.last_alert_time:
            elapsed = current_time - self.last_alert_time[alert_key]
            if elapsed < self.min_interval:
                logger.info(f"Alert rate-limited: {alert_key} (wait {self.min_interval - elapsed:.1f}s)")
                return

        self.last_alert_time[alert_key] = current_time

        # Email alert
        if self.config.get('email', {}).get('enabled', False):
            email_subject = f"🚨 Security Alert: {event_type.upper()} - {severity.upper()}"
            email_body = self._format_email_body(alert_data)

            success = self.email_sender.send(
                subject=email_subject,
                body=email_body,
                snapshot_path=snapshot_path
            )

            self._log_alert(event_id, AlertType.EMAIL, success)

        # SMS alert
        if self.config.get('sms', {}).get('enabled', False) and severity in ['high', 'critical']:
            sms_message = f"SECURITY ALERT [{severity.upper()}]: {event_type} detected on Camera {camera_id}. Risk: {risk_score}/100"

            success = self.sms_sender.send(sms_message)
            self._log_alert(event_id, AlertType.SMS, success)

        # Webhook alert
        if self.config.get('webhook', {}).get('enabled', False):
            webhook_payload = {
                'event_id': event_id,
                'event_type': event_type,
                'severity': severity,
                'camera_id': camera_id,
                'description': description,
                'risk_score': risk_score,
                'snapshot_path': snapshot_path
            }

            success = self.webhook_sender.send(webhook_payload)
            self._log_alert(event_id, AlertType.WEBHOOK, success)

        logger.info(f"Alert sent for event {event_id}: {event_type} ({severity})")

    def _format_email_body(self, alert_data: Dict[str, Any]) -> str:
        """
        Format HTML email body.

        Args:
            alert_data: Alert data

        Returns:
            HTML email body
        """
        severity = alert_data.get('severity', 'medium')
        severity_colors = {
            'low': '#4caf50',
            'medium': '#ff9800',
            'high': '#ff5722',
            'critical': '#f44336'
        }

        color = severity_colors.get(severity, '#9e9e9e')

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ background-color: white; padding: 20px; border-radius: 8px; max-width: 600px; margin: 0 auto; }}
                .header {{ background-color: {color}; color: white; padding: 15px; border-radius: 4px; text-align: center; }}
                .content {{ padding: 20px 0; }}
                .field {{ margin: 10px 0; }}
                .label {{ font-weight: bold; color: #555; }}
                .value {{ color: #333; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 Security Alert</h1>
                    <h2>{alert_data.get('event_type', 'UNKNOWN').upper()}</h2>
                </div>
                <div class="content">
                    <div class="field">
                        <span class="label">Severity:</span>
                        <span class="value" style="color: {color}; font-weight: bold;">{severity.upper()}</span>
                    </div>
                    <div class="field">
                        <span class="label">Camera:</span>
                        <span class="value">Camera {alert_data.get('camera_id', 'Unknown')}</span>
                    </div>
                    <div class="field">
                        <span class="label">Time:</span>
                        <span class="value">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                    </div>
                    <div class="field">
                        <span class="label">Risk Score:</span>
                        <span class="value">{alert_data.get('risk_score', 0)}/100</span>
                    </div>
                    <div class="field">
                        <span class="label">Description:</span>
                        <span class="value">{alert_data.get('description', 'No description')}</span>
                    </div>
                </div>
                <div class="footer">
                    <p>Multi-Camera Intrusion Detection System</p>
                    <p>This is an automated alert. Do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _log_alert(self, event_id: Optional[int], alert_type: AlertType, success: bool):
        """
        Log alert to database.

        Args:
            event_id: Associated event ID
            alert_type: Type of alert
            success: Whether alert was sent successfully
        """
        if not self.database or not event_id:
            return

        try:
            alert = Alert(
                event_id=event_id,
                alert_type=alert_type,
                recipient="system",  # TODO: Track actual recipients
                status=AlertStatus.SENT if success else AlertStatus.FAILED,
                sent_at=datetime.utcnow() if success else None,
                retry_count=0
            )

            self.database.add(alert)

        except Exception as e:
            logger.error(f"Failed to log alert: {e}")

    def trigger_alert(
        self,
        event_id: Optional[int] = None,
        event_type: str = "unknown",
        severity: str = "medium",
        description: str = "",
        camera_id: int = 0,
        snapshot_path: Optional[str] = None,
        risk_score: int = 0
    ):
        """
        Trigger an alert (adds to queue for processing).

        Args:
            event_id: Associated event ID
            event_type: Type of event
            severity: Severity level (low, medium, high, critical)
            description: Alert description
            camera_id: Camera ID
            snapshot_path: Path to snapshot image
            risk_score: Risk score (0-100)
        """
        if not self.config.get('enabled', True):
            logger.debug("Alerts disabled, skipping")
            return

        alert_data = {
            'event_id': event_id,
            'event_type': event_type,
            'severity': severity,
            'description': description,
            'camera_id': camera_id,
            'snapshot_path': snapshot_path,
            'risk_score': risk_score
        }

        self.alert_queue.put(alert_data)
        logger.info(f"Alert queued: {event_type} ({severity}) on camera {camera_id}")

    def trigger_emergency_alert(self, description: str = "Emergency alert triggered"):
        """
        Trigger emergency alert to all channels immediately.

        Args:
            description: Emergency description
        """
        logger.critical(f"EMERGENCY ALERT: {description}")

        self.trigger_alert(
            event_type="emergency",
            severity="critical",
            description=description,
            risk_score=100
        )

    def stop(self):
        """Stop alert processing."""
        logger.info("Stopping alert manager...")
        self.stop_event.set()

        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)

        logger.info("Alert manager stopped")


if __name__ == "__main__":
    # Test alert manager
    config = {
        'alerts': {
            'enabled': True,
            'email': {
                'enabled': False,  # Configure with real credentials
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'sender_email': 'test@example.com',
                'sender_password': 'password',
                'recipients': ['recipient@example.com']
            }
        }
    }

    alert_manager = AlertManager(config)

    # Test alert
    alert_manager.trigger_alert(
        event_type="intrusion",
        severity="high",
        description="Unauthorized person detected in restricted area",
        camera_id=1,
        risk_score=75
    )

    # Wait for processing
    time.sleep(2)

    alert_manager.stop()
    print("Test complete")
