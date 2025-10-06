"""
User model for the Smart Campus Attendance System
Handles Admin, Lecturer, and Student users
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    LECTURER = "lecturer"
    STUDENT = "student"


class UserStatus(str, enum.Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class User(Base):
    """
    Base User model for all user types
    Contains common fields for Admin, Lecturer, and Student
    """
    __tablename__ = "users"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Authentication & Identity
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, index=True)
    
    # Personal Information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(20), nullable=True)
    
    # Profile
    profile_photo_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    
    # Account Status
    status = Column(SQLEnum(UserStatus), default=UserStatus.PENDING, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String(255), nullable=True)
    
    # Security
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    
    # Relationships
    student_profile = relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    lecturer_profile = relationship("Lecturer", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
    
    @property
    def full_name(self) -> str:
        """Get full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_active(self) -> bool:
        """Check if user account is active"""
        return self.status == UserStatus.ACTIVE
    
    @property
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return self.role == UserRole.ADMIN
    
    @property
    def is_lecturer(self) -> bool:
        """Check if user is lecturer"""
        return self.role == UserRole.LECTURER
    
    @property
    def is_student(self) -> bool:
        """Check if user is student"""
        return self.role == UserRole.STUDENT
    
    def to_dict(self) -> dict:
        """Convert user to dictionary (exclude sensitive data)"""
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role.value,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "phone": self.phone,
            "profile_photo_url": self.profile_photo_url,
            "status": self.status.value,
            "is_email_verified": self.is_email_verified,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
        }


class Student(Base):
    """
    Student-specific profile information
    One-to-one relationship with User
    """
    __tablename__ = "students"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key to User
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    
    # Student-specific fields
    student_id = Column(String(50), unique=True, index=True, nullable=False)  # e.g., 2021-CS-1234
    enrollment_year = Column(Integer, nullable=False)
    department = Column(String(100), nullable=True)
    program = Column(String(100), nullable=True)  # e.g., Bachelor of Computer Science
    year_of_study = Column(Integer, nullable=True)  # 1, 2, 3, 4
    semester = Column(Integer, nullable=True)  # Current semester
    
    # Contact Information
    parent_name = Column(String(200), nullable=True)
    parent_phone = Column(String(20), nullable=True)
    parent_email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    
    # Academic Status
    total_credits = Column(Integer, default=0)
    
    # Face Recognition
    is_face_enrolled = Column(Boolean, default=False, nullable=False)
    face_enrollment_date = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])
    face_encodings = relationship("FaceEncoding", back_populates="student", cascade="all, delete-orphan")
    enrollments = relationship("CourseEnrollment", back_populates="student", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Student(id={self.id}, student_id={self.student_id})>"
    
    @property
    def display_id(self) -> str:
        """Get display ID"""
        return self.student_id
    
    def to_dict(self) -> dict:
        """Convert student to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "student_id": self.student_id,
            "enrollment_year": self.enrollment_year,
            "department": self.department,
            "program": self.program,
            "year_of_study": self.year_of_study,
            "semester": self.semester,
            "is_face_enrolled": self.is_face_enrolled,
            "face_enrollment_date": self.face_enrollment_date.isoformat() if self.face_enrollment_date else None,
        }


class Lecturer(Base):
    """
    Lecturer-specific profile information
    One-to-one relationship with User
    """
    __tablename__ = "lecturers"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key to User
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    
    # Lecturer-specific fields
    employee_id = Column(String(50), unique=True, index=True, nullable=False)  # e.g., EMP-2020-001
    department = Column(String(100), nullable=False)
    designation = Column(String(100), nullable=True)  # e.g., Assistant Professor, Professor
    specialization = Column(String(200), nullable=True)  # Area of expertise
    
    # Contact & Office
    office_location = Column(String(200), nullable=True)
    office_phone = Column(String(20), nullable=True)
    office_hours = Column(Text, nullable=True)  # JSON string or text
    
    # Employment Details
    hire_date = Column(DateTime, nullable=True)
    employment_type = Column(String(50), nullable=True)  # Full-time, Part-time, Contract
    
    # Academic
    qualification = Column(String(200), nullable=True)  # e.g., PhD in Computer Science
    experience_years = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="lecturer_profile", foreign_keys=[user_id])
    course_assignments = relationship("CourseAssignment", back_populates="lecturer", cascade="all, delete-orphan")
    sessions = relationship("ClassSession", back_populates="lecturer", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Lecturer(id={self.id}, employee_id={self.employee_id})>"
    
    @property
    def display_id(self) -> str:
        """Get display ID"""
        return self.employee_id
    
    def to_dict(self) -> dict:
        """Convert lecturer to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "employee_id": self.employee_id,
            "department": self.department,
            "designation": self.designation,
            "specialization": self.specialization,
            "office_location": self.office_location,
            "office_phone": self.office_phone,
            "qualification": self.qualification,
            "experience_years": self.experience_years,
        }


# Helper functions for user management
def create_student_id(enrollment_year: int, department_code: str, sequence: int) -> str:
    """
    Generate student ID
    Format: YYYY-DEPT-XXXX
    Example: 2021-CS-1234
    """
    return f"{enrollment_year}-{department_code}-{sequence:04d}"


def create_employee_id(hire_year: int, sequence: int) -> str:
    """
    Generate employee ID
    Format: EMP-YYYY-XXX
    Example: EMP-2020-001
    """
    return f"EMP-{hire_year}-{sequence:03d}"


def parse_student_id(student_id: str) -> dict:
    """
    Parse student ID to extract components
    Example: "2021-CS-1234" -> {year: 2021, dept: "CS", seq: 1234}
    """
    try:
        parts = student_id.split("-")
        return {
            "year": int(parts[0]),
            "department": parts[1],
            "sequence": int(parts[2])
        }
    except:
        return None