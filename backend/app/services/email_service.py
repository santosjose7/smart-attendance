"""
Email Service
Handles sending emails via SMTP for notifications and communications
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict
from datetime import datetime
import logging

from app.config import settings
from app.models import EmailLog, EmailType, EmailStatus, EmailPriority

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails using SMTP
    """
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_tls = settings.SMTP_TLS
        self.from_email = settings.EMAIL_FROM
        self.from_name = settings.EMAIL_FROM_NAME
        self.enabled = settings.EMAIL_ENABLED
    
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        to_name: Optional[str] = None,
        email_type: EmailType = EmailType.CUSTOM,
        priority: EmailPriority = EmailPriority.NORMAL,
        user_id: Optional[int] = None,
        db = None
    ) -> bool:
        """
        Send an email via SMTP
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML body content
            body_text: Plain text body (optional)
            to_name: Recipient name
            email_type: Type of email
            priority: Email priority
            user_id: User ID for logging
            db: Database session for logging
        
        Returns:
            True if sent successfully, False otherwise
        """
        
        if not self.enabled:
            logger.warning("Email service is disabled")
            return False
        
        if not self.smtp_user or not self.smtp_password:
            logger.error("SMTP credentials not configured")
            return False
        
        try:
            # Create email log
            email_log = None
            if db:
                email_log = EmailLog(
                    recipient_email=to_email,
                    recipient_name=to_name,
                    recipient_user_id=user_id,
                    subject=subject,
                    body_html=body_html,
                    body_text=body_text,
                    email_type=email_type,
                    priority=priority,
                    sender_email=self.from_email,
                    sender_name=self.from_name,
                    status=EmailStatus.PENDING
                )
                db.add(email_log)
                db.commit()
                db.refresh(email_log)
            
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = f"{self.from_name} <{self.from_email}>"
            message['To'] = f"{to_name} <{to_email}>" if to_name else to_email
            
            # Add plain text part
            if body_text:
                text_part = MIMEText(body_text, 'plain', 'utf-8')
                message.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(body_html, 'html', 'utf-8')
            message.attach(html_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                use_tls=self.smtp_tls
            )
            
            # Update log as sent
            if email_log:
                email_log.mark_sent()
                db.commit()
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            
            # Update log as failed
            if email_log:
                email_log.mark_failed(str(e))
                db.commit()
            
            return False
    
    
    async def send_bulk_email(
        self,
        recipients: List[Dict[str, str]],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        email_type: EmailType = EmailType.ANNOUNCEMENT,
        db = None
    ) -> Dict[str, int]:
        """
        Send bulk emails to multiple recipients
        
        Args:
            recipients: List of dicts with 'email' and optional 'name', 'user_id'
            subject: Email subject
            body_html: HTML body
            body_text: Plain text body
            email_type: Type of email
            db: Database session
        
        Returns:
            Dict with counts: {'sent': 10, 'failed': 2}
        """
        
        results = {'sent': 0, 'failed': 0}
        
        for recipient in recipients:
            success = await self.send_email(
                to_email=recipient['email'],
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                to_name=recipient.get('name'),
                email_type=email_type,
                user_id=recipient.get('user_id'),
                db=db
            )
            
            if success:
                results['sent'] += 1
            else:
                results['failed'] += 1
        
        logger.info(f"Bulk email completed: {results['sent']} sent, {results['failed']} failed")
        return results


# Email template functions

def get_email_template(content: str, title: str = "") -> str:
    """
    Wrap content in email template
    
    Args:
        content: Email content (HTML)
        title: Email title
    
    Returns:
        Complete HTML email
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
            }}
            .content {{
                background: #f9f9f9;
                padding: 30px;
                border: 1px solid #ddd;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                background: #333;
                color: #999;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                border-radius: 0 0 10px 10px;
            }}
            .info-box {{
                background: #e3f2fd;
                border-left: 4px solid #2196f3;
                padding: 15px;
                margin: 20px 0;
            }}
            .warning-box {{
                background: #fff3e0;
                border-left: 4px solid #ff9800;
                padding: 15px;
                margin: 20px 0;
            }}
            .success-box {{
                background: #e8f5e9;
                border-left: 4px solid #4caf50;
                padding: 15px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📚 Smart Campus Attendance</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>This is an automated email from Smart Campus Attendance System.</p>
            <p>If you have any questions, please contact support@campus.edu</p>
            <p>&copy; 2025 Smart Campus. All rights reserved.</p>
        </div>
    </body>
    </html>
    """


# Specific email templates

async def send_welcome_email(
    to_email: str,
    to_name: str,
    user_id: int,
    role: str,
    db = None
) -> bool:
    """Send welcome email to new user"""
    
    content = f"""
    <h2>Welcome to Smart Campus Attendance System!</h2>
    <p>Hello {to_name},</p>
    <p>Your account has been successfully created.</p>
    
    <div class="info-box">
        <strong>Your Account Details:</strong><br>
        Email: {to_email}<br>
        Role: {role.title()}
    </div>
    
    <p>Next steps:</p>
    <ul>
        <li>Verify your email address</li>
        <li>Complete your profile</li>
        {'<li>Enroll your face for attendance</li>' if role == 'student' else ''}
        <li>Start using the system</li>
    </ul>
    
    <a href="http://localhost:3000/dashboard" class="button">Go to Dashboard</a>
    
    <p>Best regards,<br>Campus Administration Team</p>
    """
    
    html = get_email_template(content, "Welcome")
    
    email_service = EmailService()
    return await email_service.send_email(
        to_email=to_email,
        subject="Welcome to Smart Campus Attendance System",
        body_html=html,
        to_name=to_name,
        email_type=EmailType.WELCOME,
        user_id=user_id,
        db=db
    )


async def send_verification_email(
    to_email: str,
    to_name: str,
    verification_token: str,
    db = None
) -> bool:
    """Send email verification link"""
    
    verify_link = f"http://localhost:3000/verify-email?token={verification_token}"
    
    content = f"""
    <h2>Verify Your Email Address</h2>
    <p>Hello {to_name},</p>
    <p>Please verify your email address by clicking the button below:</p>
    
    <a href="{verify_link}" class="button">Verify Email Address</a>
    
    <p>Or copy and paste this link into your browser:</p>
    <p style="word-break: break-all; color: #666;">{verify_link}</p>
    
    <div class="warning-box">
        <strong>⚠️ Security Note:</strong><br>
        This link will expire in 24 hours. If you didn't create this account, please ignore this email.
    </div>
    
    <p>Best regards,<br>Campus Administration Team</p>
    """
    
    html = get_email_template(content, "Verify Email")
    
    email_service = EmailService()
    return await email_service.send_email(
        to_email=to_email,
        subject="Verify Your Email Address",
        body_html=html,
        to_name=to_name,
        email_type=EmailType.EMAIL_VERIFICATION,
        db=db
    )


async def send_password_reset_email(
    to_email: str,
    to_name: str,
    reset_token: str,
    db = None
) -> bool:
    """Send password reset link"""
    
    reset_link = f"http://localhost:3000/reset-password?token={reset_token}"
    
    content = f"""
    <h2>Reset Your Password</h2>
    <p>Hello {to_name},</p>
    <p>We received a request to reset your password. Click the button below to create a new password:</p>
    
    <a href="{reset_link}" class="button">Reset Password</a>
    
    <p>Or copy and paste this link into your browser:</p>
    <p style="word-break: break-all; color: #666;">{reset_link}</p>
    
    <div class="warning-box">
        <strong>⚠️ Security Note:</strong><br>
        This link will expire in 1 hour. If you didn't request this, please ignore this email or contact support.
    </div>
    
    <p>Best regards,<br>Campus Administration Team</p>
    """
    
    html = get_email_template(content, "Reset Password")
    
    email_service = EmailService()
    return await email_service.send_email(
        to_email=to_email,
        subject="Reset Your Password",
        body_html=html,
        to_name=to_name,
        email_type=EmailType.PASSWORD_RESET,
        db=db
    )


async def send_enrollment_confirmation_email(
    to_email: str,
    to_name: str,
    student_id: str,
    photos_count: int,
    quality_grade: str,
    user_id: int,
    db = None
) -> bool:
    """Send face enrollment confirmation"""
    
    content = f"""
    <h2>Face Enrollment Completed! ✅</h2>
    <p>Hello {to_name},</p>
    <p>Your face has been successfully enrolled in the attendance system.</p>
    
    <div class="success-box">
        <strong>Enrollment Details:</strong><br>
        Student ID: {student_id}<br>
        Photos Captured: {photos_count}<br>
        Quality Grade: {quality_grade}<br>
        Date: {datetime.now().strftime('%B %d, %Y')}
    </div>
    
    <p><strong>What's Next?</strong></p>
    <ul>
        <li>You can now use face recognition to check in to classes</li>
        <li>Simply look at the camera at the classroom entrance</li>
        <li>Your attendance will be marked automatically</li>
    </ul>
    
    <p><strong>Tips for Best Results:</strong></p>
    <ul>
        <li>Look directly at the camera</li>
        <li>Ensure good lighting</li>
        <li>Check-in takes only 2-3 seconds</li>
    </ul>
    
    <p>Happy Learning!<br>Campus Administration Team</p>
    """
    
    html = get_email_template(content, "Enrollment Complete")
    
    email_service = EmailService()
    return await email_service.send_email(
        to_email=to_email,
        subject="Face Enrollment Completed Successfully",
        body_html=html,
        to_name=to_name,
        email_type=EmailType.ENROLLMENT_CONFIRMATION,
        user_id=user_id,
        db=db
    )


async def send_attendance_confirmation_email(
    to_email: str,
    to_name: str,
    course_name: str,
    check_in_time: datetime,
    status: str,
    method: str,
    user_id: int,
    db = None
) -> bool:
    """Send attendance check-in confirmation"""
    
    status_color = "#4caf50" if status == "present" else "#ff9800"
    
    content = f"""
    <h2>Attendance Marked ✓</h2>
    <p>Hello {to_name},</p>
    <p>Your attendance has been successfully recorded.</p>
    
    <div class="info-box">
        <strong>Class Details:</strong><br>
        Course: {course_name}<br>
        Time: {check_in_time.strftime('%I:%M %p')}<br>
        Status: <span style="color: {status_color}; font-weight: bold;">{status.upper()}</span><br>
        Method: {method.replace('_', ' ').title()}
    </div>
    
    <p>Keep up the good work!</p>
    
    <a href="http://localhost:3000/student/attendance" class="button">View Attendance</a>
    
    <p>Best regards,<br>Campus Attendance System</p>
    """
    
    html = get_email_template(content, "Attendance Confirmed")
    
    email_service = EmailService()
    return await email_service.send_email(
        to_email=to_email,
        subject=f"Attendance Marked - {course_name}",
        body_html=html,
        to_name=to_name,
        email_type=EmailType.ATTENDANCE_CONFIRMATION,
        user_id=user_id,
        db=db
    )


async def send_absence_alert_email(
    to_email: str,
    to_name: str,
    course_name: str,
    session_date: datetime,
    user_id: int,
    db = None
) -> bool:
    """Send absence notification"""
    
    content = f"""
    <h2>Attendance Alert</h2>
    <p>Hello {to_name},</p>
    <p>You were marked absent for the following class:</p>
    
    <div class="warning-box">
        <strong>Absence Details:</strong><br>
        Course: {course_name}<br>
        Date: {session_date.strftime('%B %d, %Y')}<br>
        Time: {session_date.strftime('%I:%M %p')}
    </div>
    
    <p>If this is an error or you have a valid reason for absence, please contact your lecturer immediately.</p>
    
    <a href="http://localhost:3000/student/attendance" class="button">View Attendance</a>
    
    <p>Best regards,<br>Campus Attendance System</p>
    """
    
    html = get_email_template(content, "Absence Alert")
    
    email_service = EmailService()
    return await email_service.send_email(
        to_email=to_email,
        subject=f"Absence Alert - {course_name}",
        body_html=html,
        to_name=to_name,
        email_type=EmailType.ABSENCE_ALERT,
        priority=EmailPriority.HIGH,
        user_id=user_id,
        db=db
    )


async def send_low_attendance_warning_email(
    to_email: str,
    to_name: str,
    course_name: str,
    attendance_percentage: float,
    classes_attended: int,
    total_classes: int,
    user_id: int,
    db = None
) -> bool:
    """Send low attendance warning"""
    
    content = f"""
    <h2>⚠️ Low Attendance Warning</h2>
    <p>Hello {to_name},</p>
    <p>Your attendance in <strong>{course_name}</strong> has fallen below the required minimum.</p>
    
    <div class="warning-box">
        <strong>Attendance Summary:</strong><br>
        Current Attendance: <strong>{attendance_percentage:.1f}%</strong><br>
        Classes Attended: {classes_attended} out of {total_classes}<br>
        Required Minimum: {settings.MINIMUM_ATTENDANCE_PERCENTAGE}%<br>
        <strong style="color: #d32f2f;">⚠️ Below Requirement</strong>
    </div>
    
    <p><strong>Action Required:</strong></p>
    <ul>
        <li>Attend all remaining classes regularly</li>
        <li>Contact your lecturer if you have concerns</li>
        <li>Monitor your attendance closely</li>
    </ul>
    
    <p>Failure to meet attendance requirements may affect your eligibility for exams.</p>
    
    <a href="http://localhost:3000/student/attendance" class="button">View Full Attendance</a>
    
    <p>Best regards,<br>Campus Administration Team</p>
    """
    
    html = get_email_template(content, "Low Attendance Warning")
    
    email_service = EmailService()
    return await email_service.send_email(
        to_email=to_email,
        subject=f"⚠️ Low Attendance Warning - {course_name}",
        body_html=html,
        to_name=to_name,
        email_type=EmailType.LOW_ATTENDANCE_WARNING,
        priority=EmailPriority.HIGH,
        user_id=user_id,
        db=db
    )


# Create singleton instance
email_service = EmailService()


# Export main items
__all__ = [
    'EmailService',
    'email_service',
    'send_welcome_email',
    'send_verification_email',
    'send_password_reset_email',
    'send_enrollment_confirmation_email',
    'send_attendance_confirmation_email',
    'send_absence_alert_email',
    'send_low_attendance_warning_email'
]