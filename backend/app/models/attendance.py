"""
Attendance model for the Smart Campus Attendance System
Tracks student attendance for each class session
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class AttendanceStatus(str, enum.Enum):
    """Attendance status enumeration"""
    PRESENT = "present"  # Student attended on time
    LATE = "late"  # Student arrived late
    ABSENT = "absent"  # Student did not attend
    EXCUSED = "excused"  # Absence excused (medical, emergency)


class CheckInMethod(str, enum.Enum):
    """Method used for check-in"""
    FACE_RECOGNITION = "face_recognition"
    QR_CODE = "qr_code"
    MANUAL = "manual"  # Marked by lecturer


class AttendanceRecord(Base):
    """
    Attendance Record model
    Tracks individual student attendance for each class session
    """
    __tablename__ = "attendance_records"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Keys
    session_id = Column(Integer, ForeignKey("class_sessions.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    
    # Attendance Status
    status = Column(SQLEnum(AttendanceStatus), nullable=False, index=True)
    check_in_method = Column(SQLEnum(CheckInMethod), nullable=True)
    
    # Timing Information
    check_in_time = Column(DateTime, nullable=True)  # When student checked in
    marked_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When record was created
    
    # Late Arrival Details
    minutes_late = Column(Integer, default=0, nullable=False)  # How many minutes late
    is_late = Column(Boolean, default=False, nullable=False)
    
    # Manual Override
    manually_marked = Column(Boolean, default=False, nullable=False)
    marked_by_lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=True)
    override_reason = Column(Text, nullable=True)  # Reason for manual marking
    
    # Excused Absence
    is_excused = Column(Boolean, default=False, nullable=False)
    excuse_reason = Column(Text, nullable=True)  # Medical, emergency, etc.
    excuse_document_url = Column(String(500), nullable=True)  # Link to medical certificate, etc.
    excuse_approved_by = Column(Integer, ForeignKey("lecturers.id"), nullable=True)
    excuse_approved_at = Column(DateTime, nullable=True)
    
    # Face Recognition Specific
    face_confidence_score = Column(Float, nullable=True)  # Confidence score of face match (0-1)
    face_encoding_id = Column(Integer, nullable=True)  # Which face encoding was matched
    
    # Location Information (optional)
    check_in_latitude = Column(Float, nullable=True)
    check_in_longitude = Column(Float, nullable=True)
    
    # Additional Notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    session = relationship("ClassSession", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")
    
    def __repr__(self):
        return f"<AttendanceRecord(id={self.id}, student_id={self.student_id}, status={self.status})>"
    
    @property
    def is_present(self) -> bool:
        """Check if student was present"""
        return self.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE]
    
    @property
    def is_absent(self) -> bool:
        """Check if student was absent"""
        return self.status == AttendanceStatus.ABSENT
    
    @property
    def attendance_display(self) -> str:
        """Get display-friendly attendance status"""
        if self.is_excused:
            return "Excused Absence"
        elif self.status == AttendanceStatus.LATE:
            return f"Late ({self.minutes_late} min)"
        else:
            return self.status.value.title()
    
    def mark_present(self, method: CheckInMethod, check_in_time: datetime = None, 
                    confidence: float = None):
        """
        Mark student as present
        
        Args:
            method: Check-in method used
            check_in_time: Time of check-in (defaults to now)
            confidence: Face recognition confidence score
        """
        self.status = AttendanceStatus.PRESENT
        self.check_in_method = method
        self.check_in_time = check_in_time or datetime.utcnow()
        if confidence:
            self.face_confidence_score = confidence
    
    def mark_late(self, minutes_late: int, method: CheckInMethod, 
                  check_in_time: datetime = None, confidence: float = None):
        """
        Mark student as late
        
        Args:
            minutes_late: How many minutes late
            method: Check-in method used
            check_in_time: Time of check-in (defaults to now)
            confidence: Face recognition confidence score
        """
        self.status = AttendanceStatus.LATE
        self.is_late = True
        self.minutes_late = minutes_late
        self.check_in_method = method
        self.check_in_time = check_in_time or datetime.utcnow()
        if confidence:
            self.face_confidence_score = confidence
    
    def mark_absent(self):
        """Mark student as absent"""
        self.status = AttendanceStatus.ABSENT
        self.check_in_time = None
    
    def excuse_absence(self, reason: str, approved_by: int = None, 
                      document_url: str = None):
        """
        Excuse an absence
        
        Args:
            reason: Reason for absence
            approved_by: Lecturer ID who approved
            document_url: Link to supporting document
        """
        self.status = AttendanceStatus.EXCUSED
        self.is_excused = True
        self.excuse_reason = reason
        self.excuse_approved_by = approved_by
        self.excuse_approved_at = datetime.utcnow()
        if document_url:
            self.excuse_document_url = document_url
    
    def manual_override(self, new_status: AttendanceStatus, lecturer_id: int, 
                       reason: str = None):
        """
        Manually override attendance status
        
        Args:
            new_status: New attendance status
            lecturer_id: Lecturer making the change
            reason: Reason for override
        """
        self.status = new_status
        self.manually_marked = True
        self.marked_by_lecturer_id = lecturer_id
        self.override_reason = reason
        self.marked_at = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert attendance record to dictionary"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "student_id": self.student_id,
            "status": self.status.value,
            "check_in_method": self.check_in_method.value if self.check_in_method else None,
            "check_in_time": self.check_in_time.isoformat() if self.check_in_time else None,
            "is_late": self.is_late,
            "minutes_late": self.minutes_late,
            "is_excused": self.is_excused,
            "excuse_reason": self.excuse_reason,
            "manually_marked": self.manually_marked,
            "face_confidence_score": round(self.face_confidence_score, 2) if self.face_confidence_score else None,
            "attendance_display": self.attendance_display,
            "marked_at": self.marked_at.isoformat(),
        }


# Helper functions for attendance statistics
def calculate_student_attendance_percentage(student_id: int, course_id: int = None) -> float:
    """
    Calculate attendance percentage for a student
    
    Args:
        student_id: Student ID
        course_id: Course ID (None for all courses)
    
    Returns:
        Attendance percentage (0-100)
    """
    # This would be implemented in a service layer with database access
    pass


def get_attendance_summary(session_id: int) -> dict:
    """
    Get attendance summary for a session
    
    Args:
        session_id: Class session ID
    
    Returns:
        Dictionary with attendance counts and percentages
    """
    # This would be implemented in a service layer with database access
    pass


def get_student_attendance_history(student_id: int, course_id: int = None, 
                                   limit: int = 50) -> list:
    """
    Get attendance history for a student
    
    Args:
        student_id: Student ID
        course_id: Course ID (None for all courses)
        limit: Maximum number of records
    
    Returns:
        List of attendance records
    """
    # This would be implemented in a service layer with database access
    pass


def get_low_attendance_students(course_id: int, threshold: float = 75.0) -> list:
    """
    Get students with attendance below threshold
    
    Args:
        course_id: Course ID
        threshold: Minimum attendance percentage
    
    Returns:
        List of students with low attendance
    """
    # This would be implemented in a service layer with database access
    pass


def mark_absent_students(session_id: int):
    """
    Automatically mark students as absent who didn't check in
    Should be called when a session ends
    
    Args:
        session_id: Class session ID
    """
    # This would be implemented in a service layer with database access
    pass


def calculate_late_minutes(check_in_time: datetime, session_start_time: datetime) -> int:
    """
    Calculate how many minutes late a student is
    
    Args:
        check_in_time: When student checked in
        session_start_time: When class started
    
    Returns:
        Number of minutes late (0 if on time)
    """
    if check_in_time <= session_start_time:
        return 0
    
    delta = check_in_time - session_start_time
    return int(delta.total_seconds() / 60)


def is_check_in_late(check_in_time: datetime, session_start_time: datetime, 
                    late_threshold_minutes: int = 5) -> bool:
    """
    Determine if a check-in should be marked as late
    
    Args:
        check_in_time: When student checked in
        session_start_time: When class started
        late_threshold_minutes: Minutes after start to be considered late
    
    Returns:
        True if late, False otherwise
    """
    minutes_late = calculate_late_minutes(check_in_time, session_start_time)
    return minutes_late > late_threshold_minutes


# Statistics and analytics functions
class AttendanceStats:
    """
    Helper class for attendance statistics
    """
    
    @staticmethod
    def get_course_attendance_rate(course_id: int) -> dict:
        """
        Get overall attendance rate for a course
        
        Returns:
            Dictionary with attendance statistics
        """
        return {
            "total_sessions": 0,
            "average_attendance": 0.0,
            "present_count": 0,
            "absent_count": 0,
            "late_count": 0,
            "excused_count": 0
        }
    
    @staticmethod
    def get_student_attendance_trends(student_id: int, days: int = 30) -> list:
        """
        Get attendance trends for a student over time
        
        Args:
            student_id: Student ID
            days: Number of days to analyze
        
        Returns:
            List of attendance data points
        """
        return []
    
    @staticmethod
    def get_best_attending_students(course_id: int, limit: int = 10) -> list:
        """
        Get students with best attendance
        
        Args:
            course_id: Course ID
            limit: Number of students to return
        
        Returns:
            List of top attending students
        """
        return []
    
    @staticmethod
    def get_punctuality_stats(course_id: int) -> dict:
        """
        Get punctuality statistics for a course
        
        Returns:
            Dictionary with late arrival statistics
        """
        return {
            "average_late_minutes": 0.0,
            "late_percentage": 0.0,
            "most_common_late_time": None
        }