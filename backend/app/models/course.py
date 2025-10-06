"""
Course and Enrollment models for the Smart Campus Attendance System
Handles courses, sections, enrollments, and course assignments
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class CourseStatus(str, enum.Enum):
    """Course status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DRAFT = "draft"


class EnrollmentStatus(str, enum.Enum):
    """Enrollment status for students"""
    ENROLLED = "enrolled"
    DROPPED = "dropped"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"


class Course(Base):
    """
    Course model representing a course offered by the institution
    """
    __tablename__ = "courses"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Course Information
    course_code = Column(String(20), unique=True, index=True, nullable=False)  # e.g., CS101
    course_name = Column(String(200), nullable=False)  # e.g., Introduction to Programming
    description = Column(Text, nullable=True)
    
    # Academic Details
    department = Column(String(100), nullable=False)
    credit_hours = Column(Integer, nullable=False)
    semester = Column(String(20), nullable=False)  # e.g., Fall 2024, Spring 2025
    academic_year = Column(String(10), nullable=False)  # e.g., 2024-2025
    
    # Course Settings
    max_capacity = Column(Integer, nullable=True)  # Maximum students per course
    prerequisites = Column(Text, nullable=True)  # Comma-separated course codes or JSON
    status = Column(SQLEnum(CourseStatus), default=CourseStatus.ACTIVE, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    sections = relationship("CourseSection", back_populates="course", cascade="all, delete-orphan")
    enrollments = relationship("CourseEnrollment", back_populates="course", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Course(id={self.id}, code={self.course_code}, name={self.course_name})>"
    
    @property
    def is_active(self) -> bool:
        """Check if course is active"""
        return self.status == CourseStatus.ACTIVE
    
    @property
    def total_students(self) -> int:
        """Get total enrolled students"""
        return len([e for e in self.enrollments if e.status == EnrollmentStatus.ENROLLED])
    
    def to_dict(self) -> dict:
        """Convert course to dictionary"""
        return {
            "id": self.id,
            "course_code": self.course_code,
            "course_name": self.course_name,
            "description": self.description,
            "department": self.department,
            "credit_hours": self.credit_hours,
            "semester": self.semester,
            "academic_year": self.academic_year,
            "max_capacity": self.max_capacity,
            "status": self.status.value,
            "total_students": self.total_students,
            "created_at": self.created_at.isoformat(),
        }


class CourseSection(Base):
    """
    Course section model for different sections of the same course
    Example: CS101 Section A, CS101 Section B
    """
    __tablename__ = "course_sections"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    
    # Section Information
    section_name = Column(String(50), nullable=False)  # e.g., A, B, Morning, Evening
    section_code = Column(String(50), nullable=True)  # e.g., CS101-A
    
    # Schedule Information
    room_number = Column(String(50), nullable=True)
    building = Column(String(100), nullable=True)
    schedule_days = Column(String(50), nullable=True)  # e.g., "Mon,Wed,Fri" or JSON
    start_time = Column(String(10), nullable=True)  # e.g., "09:00"
    end_time = Column(String(10), nullable=True)  # e.g., "10:30"
    
    # Capacity
    max_students = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    course = relationship("Course", back_populates="sections")
    assignments = relationship("CourseAssignment", back_populates="section", cascade="all, delete-orphan")
    sessions = relationship("ClassSession", back_populates="section", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CourseSection(id={self.id}, section={self.section_name})>"
    
    @property
    def full_name(self) -> str:
        """Get full section name"""
        return f"{self.course.course_code} - Section {self.section_name}"
    
    def to_dict(self) -> dict:
        """Convert section to dictionary"""
        return {
            "id": self.id,
            "course_id": self.course_id,
            "section_name": self.section_name,
            "section_code": self.section_code,
            "room_number": self.room_number,
            "building": self.building,
            "schedule_days": self.schedule_days,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "max_students": self.max_students,
            "is_active": self.is_active,
        }


class CourseEnrollment(Base):
    """
    Student enrollment in courses
    Links students to courses
    """
    __tablename__ = "course_enrollments"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Keys
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    
    # Enrollment Information
    enrollment_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.ENROLLED, nullable=False)
    
    # Drop/Withdrawal
    drop_date = Column(DateTime, nullable=True)
    drop_reason = Column(Text, nullable=True)
    
    # Attendance Tracking
    total_classes = Column(Integer, default=0)
    classes_attended = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    
    def __repr__(self):
        return f"<CourseEnrollment(id={self.id}, student_id={self.student_id}, course_id={self.course_id})>"
    
    @property
    def attendance_percentage(self) -> float:
        """Calculate attendance percentage"""
        if self.total_classes == 0:
            return 0.0
        return (self.classes_attended / self.total_classes) * 100
    
    @property
    def is_enrolled(self) -> bool:
        """Check if student is currently enrolled"""
        return self.status == EnrollmentStatus.ENROLLED
    
    def to_dict(self) -> dict:
        """Convert enrollment to dictionary"""
        return {
            "id": self.id,
            "student_id": self.student_id,
            "course_id": self.course_id,
            "enrollment_date": self.enrollment_date.isoformat(),
            "status": self.status.value,
            "total_classes": self.total_classes,
            "classes_attended": self.classes_attended,
            "attendance_percentage": round(self.attendance_percentage, 2),
        }


class CourseAssignment(Base):
    """
    Lecturer assignment to course sections
    Links lecturers to specific course sections they teach
    """
    __tablename__ = "course_assignments"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Keys
    lecturer_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("course_sections.id"), nullable=False, index=True)
    
    # Assignment Information
    assignment_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    role = Column(String(50), default="primary", nullable=False)  # primary, assistant, guest
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    lecturer = relationship("Lecturer", back_populates="course_assignments")
    section = relationship("CourseSection", back_populates="assignments")
    
    def __repr__(self):
        return f"<CourseAssignment(id={self.id}, lecturer_id={self.lecturer_id}, section_id={self.section_id})>"
    
    def to_dict(self) -> dict:
        """Convert assignment to dictionary"""
        return {
            "id": self.id,
            "lecturer_id": self.lecturer_id,
            "section_id": self.section_id,
            "assignment_date": self.assignment_date.isoformat(),
            "role": self.role,
            "is_active": self.is_active,
        }


# Helper functions
def generate_course_code(department: str, course_number: int) -> str:
    """
    Generate course code
    Example: CS + 101 -> CS101
    """
    return f"{department.upper()}{course_number}"


def parse_schedule_days(days_string: str) -> list:
    """
    Parse schedule days string to list
    Example: "Mon,Wed,Fri" -> ["Mon", "Wed", "Fri"]
    """
    if not days_string:
        return []
    return [day.strip() for day in days_string.split(",")]


def format_schedule_days(days_list: list) -> str:
    """
    Format days list to string
    Example: ["Mon", "Wed", "Fri"] -> "Mon,Wed,Fri"
    """
    return ",".join(days_list)


def get_semester_string(year: int, term: str) -> str:
    """
    Generate semester string
    Example: 2024, "Fall" -> "Fall 2024"
    """
    return f"{term} {year}"


def get_academic_year_string(start_year: int) -> str:
    """
    Generate academic year string
    Example: 2024 -> "2024-2025"
    """
    return f"{start_year}-{start_year + 1}"