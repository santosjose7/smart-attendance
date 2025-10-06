"""
Email Log model for the Smart Campus Attendance System
Tracks all emails sent by the system for monitoring and debugging
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class EmailStatus(str, enum.Enum):
    """Email delivery status"""
    PENDING = "pending"  # Queued for sending
    SENT = "sent"  # Successfully sent
    FAILED = "failed"  # Failed to send
    BOUNCED = "bounced"  # Email bounced
    DELIVERED = "delivered"  # Confirmed delivery
    OPENED = "opened"  # Recipient opened email
    CLICKED = "clicked"  # Recipient clicked link in email


class EmailType(str, enum.Enum):
    """Types of emails sent by the system"""
    WELCOME = "welcome"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
    ENROLLMENT_CONFIRMATION = "enrollment_confirmation"
    ATTENDANCE_CONFIRMATION = "attendance_confirmation"
    ABSENCE_ALERT = "absence_alert"
    LOW_ATTENDANCE_WARNING = "low_attendance_warning"
    WEEKLY_SUMMARY = "weekly_summary"
    DAILY_SUMMARY = "daily_summary"
    COURSE_ASSIGNMENT = "course_assignment"
    SYSTEM_ALERT = "system_alert"
    ANNOUNCEMENT = "announcement"
    CUSTOM = "custom"


class EmailPriority(str, enum.Enum):
    """Email priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class EmailLog(Base):
    """
    Email Log model
    Tracks all emails sent by the system
    """
    __tablename__ = "email_logs"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Recipient Information
    recipient_email = Column(String(255), nullable=False, index=True)
    recipient_name = Column(String(200), nullable=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Email Content
    email_type = Column(SQLEnum(EmailType), nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    body_text = Column(Text, nullable=True)  # Plain text version
    body_html = Column(Text, nullable=True)  # HTML version
    
    # Sender Information
    sender_email = Column(String(255), nullable=False)
    sender_name = Column(String(200), nullable=True)
    reply_to = Column(String(255), nullable=True)
    
    # Email Metadata
    priority = Column(SQLEnum(EmailPriority), default=EmailPriority.NORMAL, nullable=False)
    template_name = Column(String(100), nullable=True)  # Template used
    template_variables = Column(Text, nullable=True)  # JSON string of variables
    
    # Attachments
    has_attachments = Column(Boolean, default=False)
    attachment_urls = Column(Text, nullable=True)  # Comma-separated URLs or JSON
    
    # Delivery Status
    status = Column(SQLEnum(EmailStatus), default=EmailStatus.PENDING, nullable=False, index=True)
    
    # Sending Information
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    bounced_at = Column(DateTime, nullable=True)
    
    # Error Handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    
    # SMTP/Email Service Details
    message_id = Column(String(255), nullable=True)  # External message ID
    smtp_response = Column(Text, nullable=True)
    
    # Tracking
    open_count = Column(Integer, default=0)  # How many times opened
    click_count = Column(Integer, default=0)  # How many times links clicked
    
    # Related Records
    related_session_id = Column(Integer, nullable=True)  # For attendance emails
    related_course_id = Column(Integer, nullable=True)  # For course emails
    
    # Bulk Email
    is_bulk_email = Column(Boolean, default=False)
    bulk_email_batch_id = Column(String(100), nullable=True)  # Group bulk emails
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<EmailLog(id={self.id}, to={self.recipient_email}, type={self.email_type}, status={self.status})>"
    
    @property
    def is_sent(self) -> bool:
        """Check if email was sent"""
        return self.status in [EmailStatus.SENT, EmailStatus.DELIVERED, EmailStatus.OPENED, EmailStatus.CLICKED]
    
    @property
    def is_failed(self) -> bool:
        """Check if email failed"""
        return self.status in [EmailStatus.FAILED, EmailStatus.BOUNCED]
    
    @property
    def can_retry(self) -> bool:
        """Check if email can be retried"""
        return self.is_failed and self.retry_count < self.max_retries
    
    @property
    def is_opened(self) -> bool:
        """Check if email was opened by recipient"""
        return self.status in [EmailStatus.OPENED, EmailStatus.CLICKED]
    
    @property
    def delivery_time(self) -> int:
        """Get delivery time in seconds"""
        if self.sent_at and self.delivered_at:
            delta = self.delivered_at - self.sent_at
            return int(delta.total_seconds())
        return 0
    
    @property
    def time_to_open(self) -> int:
        """Get time from delivery to open in seconds"""
        if self.delivered_at and self.opened_at:
            delta = self.opened_at - self.delivered_at
            return int(delta.total_seconds())
        return 0
    
    def mark_sent(self, message_id: str = None, smtp_response: str = None):
        """
        Mark email as sent
        
        Args:
            message_id: External message ID
            smtp_response: SMTP server response
        """
        self.status = EmailStatus.SENT
        self.sent_at = datetime.utcnow()
        if message_id:
            self.message_id = message_id
        if smtp_response:
            self.smtp_response = smtp_response
    
    def mark_delivered(self):
        """Mark email as delivered"""
        self.status = EmailStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
    
    def mark_opened(self):
        """Mark email as opened"""
        if self.status != EmailStatus.CLICKED:  # Don't override clicked status
            self.status = EmailStatus.OPENED
        self.opened_at = datetime.utcnow()
        self.open_count += 1
    
    def mark_clicked(self):
        """Mark email link as clicked"""
        self.status = EmailStatus.CLICKED
        self.clicked_at = datetime.utcnow()
        self.click_count += 1
    
    def mark_failed(self, error_message: str):
        """
        Mark email as failed
        
        Args:
            error_message: Error description
        """
        self.status = EmailStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1
        
        # Schedule retry if within limit
        if self.can_retry:
            from datetime import timedelta
            # Exponential backoff: 5 min, 15 min, 45 min
            retry_delay = 5 * (3 ** self.retry_count)
            self.next_retry_at = datetime.utcnow() + timedelta(minutes=retry_delay)
    
    def mark_bounced(self, error_message: str = None):
        """
        Mark email as bounced
        
        Args:
            error_message: Bounce reason
        """
        self.status = EmailStatus.BOUNCED
        self.bounced_at = datetime.utcnow()
        if error_message:
            self.error_message = error_message
    
    def to_dict(self) -> dict:
        """Convert email log to dictionary"""
        return {
            "id": self.id,
            "recipient_email": self.recipient_email,
            "recipient_name": self.recipient_name,
            "email_type": self.email_type.value,
            "subject": self.subject,
            "status": self.status.value,
            "priority": self.priority.value,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "is_opened": self.is_opened,
            "open_count": self.open_count,
            "click_count": self.click_count,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
        }


# Helper functions for email logging
def log_email(
    recipient_email: str,
    subject: str,
    email_type: EmailType,
    body_text: str = None,
    body_html: str = None,
    recipient_user_id: int = None,
    priority: EmailPriority = EmailPriority.NORMAL,
    template_name: str = None
) -> EmailLog:
    """
    Create a new email log entry
    
    Args:
        recipient_email: Recipient email address
        subject: Email subject
        email_type: Type of email
        body_text: Plain text body
        body_html: HTML body
        recipient_user_id: User ID of recipient
        priority: Email priority
        template_name: Template used
    
    Returns:
        EmailLog object (not yet saved to database)
    """
    from app.config import settings
    
    return EmailLog(
        recipient_email=recipient_email,
        subject=subject,
        email_type=email_type,
        body_text=body_text,
        body_html=body_html,
        recipient_user_id=recipient_user_id,
        priority=priority,
        template_name=template_name,
        sender_email=settings.EMAIL_FROM,
        sender_name=settings.EMAIL_FROM_NAME,
    )


def get_failed_emails(limit: int = 100) -> list:
    """
    Get failed emails that can be retried
    
    Args:
        limit: Maximum number of emails to return
    
    Returns:
        List of EmailLog objects
    """
    # This would be implemented in a service layer with database access
    pass


def get_email_statistics(days: int = 30) -> dict:
    """
    Get email statistics for the last N days
    
    Args:
        days: Number of days to analyze
    
    Returns:
        Dictionary with email statistics
    """
    return {
        "total_sent": 0,
        "total_delivered": 0,
        "total_opened": 0,
        "total_clicked": 0,
        "total_failed": 0,
        "total_bounced": 0,
        "delivery_rate": 0.0,
        "open_rate": 0.0,
        "click_rate": 0.0,
        "average_delivery_time": 0,
        "by_type": {}
    }


def get_user_email_history(user_id: int, limit: int = 50) -> list:
    """
    Get email history for a user
    
    Args:
        user_id: User ID
        limit: Maximum number of emails
    
    Returns:
        List of EmailLog objects
    """
    # This would be implemented in a service layer with database access
    pass


def cleanup_old_emails(days: int = 90):
    """
    Clean up old email logs (hard delete)
    
    Args:
        days: Keep emails newer than this many days
    """
    # This would be implemented in a service layer with database access
    pass


def get_bounce_statistics() -> dict:
    """
    Get email bounce statistics
    
    Returns:
        Dictionary with bounce analysis
    """
    return {
        "total_bounces": 0,
        "bounce_rate": 0.0,
        "bounced_addresses": [],
        "common_bounce_reasons": []
    }


# Email analytics functions
class EmailAnalytics:
    """Helper class for email analytics"""
    
    @staticmethod
    def calculate_engagement_rate(email_type: EmailType = None) -> dict:
        """
        Calculate email engagement rates
        
        Args:
            email_type: Specific email type (None for all)
        
        Returns:
            Dictionary with engagement metrics
        """
        return {
            "open_rate": 0.0,
            "click_rate": 0.0,
            "bounce_rate": 0.0,
            "delivery_rate": 0.0
        }
    
    @staticmethod
    def get_best_send_times() -> dict:
        """
        Analyze best times to send emails based on open rates
        
        Returns:
            Dictionary with recommended send times
        """
        return {
            "best_hour": None,
            "best_day": None,
            "open_rates_by_hour": {},
            "open_rates_by_day": {}
        }
    
    @staticmethod
    def get_email_performance_by_type() -> list:
        """
        Get performance metrics for each email type
        
        Returns:
            List of email type performance data
        """
        return []