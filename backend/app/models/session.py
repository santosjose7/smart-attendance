"""
Class Session model for the Smart Campus Attendance System
Represents individual class meetings/sessions
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum

from app.database import Base


class SessionStatus(str, enum.Enum):
    """Class session status enumeration"""
    SCHEDULED = "scheduled"  # Session is scheduled but hasn't started
    IN_PROGRESS = "in_progress"  # Session is currently active
    COMPLETED = "completed"  # Session has ended
    CANCELLED = "cancelled"  # Session was cancelled
    POSTPONED = "postponed"  # Session was postponed


class ClassSession(Base):
    """
    Class Session model representing an individual class meeting
    Each session is a specific occurrence of a course section
    """
    __tablename__ = "class_sessions"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Keys
    section_id = Column(Integer, ForeignKey("course_sections.id"), nullable=False, index=True)
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False, index=True)
    
    # Session Information
    session_date = Column(DateTime, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    
    # Location
    room_number = Column(String(50), nullable=True)
    building = Column(String(100), nullable=True)
    
    # Session Details
    topic = Column(String(300), nullable=True)  # Topic/chapter covered
    notes = Column(Text, nullable=True)  # Additional notes
    session_type = Column(String(50), default="lecture", nullable=False)  # lecture, lab, tutorial, exam
    
    # Status
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.SCHEDULED, nullable=False)
    
    # Attendance Settings
    attendance_enabled = Column(Boolean, default=True, nullable=False)
    check_in_started_at = Column(DateTime, nullable=True)
    check_in_ended_at = Column(DateTime, nullable=True)
    
    # QR Code for attendance
    qr_code_data = Column(Text, nullable=True)  # Encrypted QR code data
    qr_code_generated_at = Column(DateTime, nullable=True)
    qr_code_expires_at = Column(DateTime, nullable=True)
    
    # Statistics (cached for performance)
    total_students = Column(Integer, default=0)  # Total enrolled students
    present_count = Column(Integer, default=0)  # Students marked present
    absent_count = Column(Integer, default=0)  # Students marked absent
    late_count = Column(Integer, default=0)  # Students marked late
    
    # Cancellation/Postponement
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    postponed_to = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    section = relationship("CourseSection", back_populates="sessions")
    lecturer = relationship("Lecturer", back_populates="sessions")
    attendance_records = relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ClassSession(id={self.id}, date={self.session_date}, status={self.status})>"
    
    @property
    def is_scheduled(self) -> bool:
        """Check if session is scheduled"""
        return self.status == SessionStatus.SCHEDULED
    
    @property
    def is_in_progress(self) -> bool:
        """Check if session is currently in progress"""
        return self.status == SessionStatus.IN_PROGRESS
    
    @property
    def is_completed(self) -> bool:
        """Check if session is completed"""
        return self.status == SessionStatus.COMPLETED
    
    @property
    def is_cancelled(self) -> bool:
        """Check if session is cancelled"""
        return self.status == SessionStatus.CANCELLED
    
    @property
    def duration_minutes(self) -> int:
        """Get session duration in minutes"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0
    
    @property
    def attendance_percentage(self) -> float:
        """Calculate attendance percentage"""
        if self.total_students == 0:
            return 0.0
        return (self.present_count / self.total_students) * 100
    
    @property
    def can_check_in(self) -> bool:
        """Check if students can currently check in"""
        if not self.attendance_enabled or self.status != SessionStatus.IN_PROGRESS:
            return False
        
        now = datetime.utcnow()
        if self.check_in_started_at and self.check_in_ended_at:
            return self.check_in_started_at <= now <= self.check_in_ended_at
        return True
    
    @property
    def is_qr_code_valid(self) -> bool:
        """Check if QR code is still valid"""
        if not self.qr_code_data or not self.qr_code_expires_at:
            return False
        return datetime.utcnow() < self.qr_code_expires_at
    
    def start_session(self, check_in_window_before: int = 10, check_in_window_after: int = 15):
        """
        Start the session and enable check-in
        
        Args:
            check_in_window_before: Minutes before start_time to allow check-in
            check_in_window_after: Minutes after start_time to allow check-in
        """
        self.status = SessionStatus.IN_PROGRESS
        self.check_in_started_at = self.start_time - timedelta(minutes=check_in_window_before)
        self.check_in_ended_at = self.start_time + timedelta(minutes=check_in_window_after)
    
    def end_session(self):
        """End the session and disable check-in"""
        self.status = SessionStatus.COMPLETED
        self.check_in_ended_at = datetime.utcnow()
    
    def cancel_session(self, reason: str = None):
        """Cancel the session"""
        self.status = SessionStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancellation_reason = reason
    
    def postpone_session(self, new_datetime: datetime, reason: str = None):
        """Postpone the session to a new date/time"""
        self.status = SessionStatus.POSTPONED
        self.postponed_to = new_datetime
        self.cancellation_reason = reason
    
    def generate_qr_code(self, expiry_minutes: int = 15) -> str:
        """
        Generate QR code data for attendance
        
        Args:
            expiry_minutes: Minutes until QR code expires
        
        Returns:
            Encrypted QR code data string
        """
        import secrets
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        # Create QR code data (to be encrypted in production)
        qr_data = f"session:{self.id}:token:{token}"
        
        self.qr_code_data = qr_data
        self.qr_code_generated_at = datetime.utcnow()
        self.qr_code_expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
        
        return qr_data
    
    def update_attendance_stats(self):
        """Update cached attendance statistics"""
        # Count attendance by status
        present = len([r for r in self.attendance_records if r.status == "present"])
        late = len([r for r in self.attendance_records if r.status == "late"])
        absent = len([r for r in self.attendance_records if r.status == "absent"])
        
        self.present_count = present
        self.late_count = late
        self.absent_count = absent
        # Assuming absent_count includes those who didn't check in
    
    def to_dict(self) -> dict:
        """Convert session to dictionary"""
        return {
            "id": self.id,
            "section_id": self.section_id,
            "lecturer_id": self.lecturer_id,
            "session_date": self.session_date.isoformat(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "room_number": self.room_number,
            "building": self.building,
            "topic": self.topic,
            "session_type": self.session_type,
            "status": self.status.value,
            "attendance_enabled": self.attendance_enabled,
            "can_check_in": self.can_check_in,
            "is_qr_code_valid": self.is_qr_code_valid,
            "total_students": self.total_students,
            "present_count": self.present_count,
            "absent_count": self.absent_count,
            "late_count": self.late_count,
            "attendance_percentage": round(self.attendance_percentage, 2),
            "duration_minutes": self.duration_minutes,
        }


# Helper functions
def create_session_schedule(
    section_id: int,
    lecturer_id: int,
    start_date: datetime,
    end_date: datetime,
    days_of_week: list,
    start_time: str,
    end_time: str,
    room_number: str = None,
    building: str = None
) -> list:
    """
    Create multiple sessions based on a schedule
    
    Args:
        section_id: Course section ID
        lecturer_id: Lecturer ID
        start_date: Semester start date
        end_date: Semester end date
        days_of_week: List of weekday numbers (0=Monday, 6=Sunday)
        start_time: Session start time (HH:MM format)
        end_time: Session end time (HH:MM format)
        room_number: Room number
        building: Building name
    
    Returns:
        List of ClassSession objects (not yet saved to database)
    """
    from datetime import time
    
    sessions = []
    current_date = start_date
    
    # Parse time strings
    start_hour, start_minute = map(int, start_time.split(":"))
    end_hour, end_minute = map(int, end_time.split(":"))
    
    while current_date <= end_date:
        # Check if current day is in the schedule
        if current_date.weekday() in days_of_week:
            session_start = datetime.combine(current_date, time(start_hour, start_minute))
            session_end = datetime.combine(current_date, time(end_hour, end_minute))
            
            session = ClassSession(
                section_id=section_id,
                lecturer_id=lecturer_id,
                session_date=current_date,
                start_time=session_start,
                end_time=session_end,
                room_number=room_number,
                building=building,
                status=SessionStatus.SCHEDULED
            )
            sessions.append(session)
        
        # Move to next day
        current_date += timedelta(days=1)
    
    return sessions


def get_upcoming_sessions(lecturer_id: int = None, days: int = 7) -> list:
    """
    Get upcoming sessions for a lecturer
    
    Args:
        lecturer_id: Lecturer ID (None for all lecturers)
        days: Number of days to look ahead
    
    Returns:
        List of upcoming ClassSession objects
    """
    # This would be implemented in a service layer with database access
    pass


def get_session_conflicts(
    lecturer_id: int,
    session_date: datetime,
    start_time: datetime,
    end_time: datetime
) -> bool:
    """
    Check if a lecturer has conflicting sessions
    
    Args:
        lecturer_id: Lecturer ID
        session_date: Date of new session
        start_time: Start time of new session
        end_time: End time of new session
    
    Returns:
        True if there are conflicts, False otherwise
    """
    # This would be implemented in a service layer with database access
    pass