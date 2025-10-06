"""
Models package initialization
Imports and exports all database models for the Smart Campus Attendance System
"""

from app.database import Base

# Import all models to register them with SQLAlchemy
from app.models.user import (
    User,
    Student,
    Lecturer,
    UserRole,
    UserStatus,
    create_student_id,
    create_employee_id,
    parse_student_id
)

from app.models.course import (
    Course,
    CourseSection,
    CourseEnrollment,
    CourseAssignment,
    CourseStatus,
    EnrollmentStatus,
    generate_course_code,
    parse_schedule_days,
    format_schedule_days,
    get_semester_string,
    get_academic_year_string
)

from app.models.session import (
    ClassSession,
    SessionStatus,
    create_session_schedule,
    get_upcoming_sessions,
    get_session_conflicts
)

from app.models.attendance import (
    AttendanceRecord,
    AttendanceStatus,
    CheckInMethod,
    calculate_student_attendance_percentage,
    get_attendance_summary,
    get_student_attendance_history,
    get_low_attendance_students,
    mark_absent_students,
    calculate_late_minutes,
    is_check_in_late,
    AttendanceStats
)

from app.models.face_encoding import (
    FaceEncoding,
    serialize_encoding,
    deserialize_encoding,
    calculate_encoding_distance,
    is_same_face,
    find_best_match,
    calculate_quality_score,
    select_best_encodings,
    check_duplicate_photo,
    get_encoding_statistics
)

from app.models.email_log import (
    EmailLog,
    EmailStatus,
    EmailType,
    EmailPriority,
    log_email,
    get_failed_emails,
    get_email_statistics,
    get_user_email_history,
    cleanup_old_emails,
    get_bounce_statistics,
    EmailAnalytics
)


# Export all models for easy import
__all__ = [
    # Base
    "Base",
    
    # User Models
    "User",
    "Student",
    "Lecturer",
    "UserRole",
    "UserStatus",
    
    # Course Models
    "Course",
    "CourseSection",
    "CourseEnrollment",
    "CourseAssignment",
    "CourseStatus",
    "EnrollmentStatus",
    
    # Session Models
    "ClassSession",
    "SessionStatus",
    
    # Attendance Models
    "AttendanceRecord",
    "AttendanceStatus",
    "CheckInMethod",
    "AttendanceStats",
    
    # Face Encoding Models
    "FaceEncoding",
    
    # Email Log Models
    "EmailLog",
    "EmailStatus",
    "EmailType",
    "EmailPriority",
    "EmailAnalytics",
    
    # User Helper Functions
    "create_student_id",
    "create_employee_id",
    "parse_student_id",
    
    # Course Helper Functions
    "generate_course_code",
    "parse_schedule_days",
    "format_schedule_days",
    "get_semester_string",
    "get_academic_year_string",
    
    # Session Helper Functions
    "create_session_schedule",
    "get_upcoming_sessions",
    "get_session_conflicts",
    
    # Attendance Helper Functions
    "calculate_student_attendance_percentage",
    "get_attendance_summary",
    "get_student_attendance_history",
    "get_low_attendance_students",
    "mark_absent_students",
    "calculate_late_minutes",
    "is_check_in_late",
    
    # Face Encoding Helper Functions
    "serialize_encoding",
    "deserialize_encoding",
    "calculate_encoding_distance",
    "is_same_face",
    "find_best_match",
    "calculate_quality_score",
    "select_best_encodings",
    "check_duplicate_photo",
    "get_encoding_statistics",
    
    # Email Helper Functions
    "log_email",
    "get_failed_emails",
    "get_email_statistics",
    "get_user_email_history",
    "cleanup_old_emails",
    "get_bounce_statistics",
]


# Model relationships summary (for documentation)
"""
DATABASE RELATIONSHIPS:

User (1) ←→ (1) Student
User (1) ←→ (1) Lecturer

Student (1) ←→ (M) FaceEncoding
Student (1) ←→ (M) CourseEnrollment
Student (1) ←→ (M) AttendanceRecord

Lecturer (1) ←→ (M) CourseAssignment
Lecturer (1) ←→ (M) ClassSession

Course (1) ←→ (M) CourseSection
Course (1) ←→ (M) CourseEnrollment

CourseSection (1) ←→ (M) CourseAssignment
CourseSection (1) ←→ (M) ClassSession

ClassSession (1) ←→ (M) AttendanceRecord

User (1) ←→ (M) EmailLog (as recipient)
"""


# Initialization check
def verify_models_loaded():
    """
    Verify that all models are properly loaded
    Returns True if all models are registered with SQLAlchemy
    """
    expected_tables = {
        "users",
        "students",
        "lecturers",
        "courses",
        "course_sections",
        "course_enrollments",
        "course_assignments",
        "class_sessions",
        "attendance_records",
        "face_encodings",
        "email_logs"
    }
    
    registered_tables = set(Base.metadata.tables.keys())
    
    missing_tables = expected_tables - registered_tables
    
    if missing_tables:
        print(f"⚠️  Warning: Missing tables: {missing_tables}")
        return False
    
    print(f"✓ All {len(expected_tables)} models loaded successfully")
    return True


# Quick model reference
MODEL_INFO = {
    "users": {
        "model": User,
        "description": "Base user model for all user types",
        "roles": ["admin", "lecturer", "student"]
    },
    "students": {
        "model": Student,
        "description": "Student-specific profile information",
        "related_to": ["users", "face_encodings", "course_enrollments", "attendance_records"]
    },
    "lecturers": {
        "model": Lecturer,
        "description": "Lecturer-specific profile information",
        "related_to": ["users", "course_assignments", "class_sessions"]
    },
    "courses": {
        "model": Course,
        "description": "Course information",
        "related_to": ["course_sections", "course_enrollments"]
    },
    "course_sections": {
        "model": CourseSection,
        "description": "Course sections (e.g., Section A, B)",
        "related_to": ["courses", "course_assignments", "class_sessions"]
    },
    "course_enrollments": {
        "model": CourseEnrollment,
        "description": "Student enrollment in courses",
        "related_to": ["students", "courses"]
    },
    "course_assignments": {
        "model": CourseAssignment,
        "description": "Lecturer assignment to course sections",
        "related_to": ["lecturers", "course_sections"]
    },
    "class_sessions": {
        "model": ClassSession,
        "description": "Individual class meetings",
        "related_to": ["course_sections", "lecturers", "attendance_records"]
    },
    "attendance_records": {
        "model": AttendanceRecord,
        "description": "Student attendance for each session",
        "related_to": ["students", "class_sessions"]
    },
    "face_encodings": {
        "model": FaceEncoding,
        "description": "Face recognition data for students",
        "related_to": ["students"]
    },
    "email_logs": {
        "model": EmailLog,
        "description": "Email tracking and logging",
        "related_to": ["users"]
    }
}


def get_model_info(table_name: str = None):
    """
    Get information about models
    
    Args:
        table_name: Specific table name (None for all)
    
    Returns:
        Model information dictionary
    """
    if table_name:
        return MODEL_INFO.get(table_name)
    return MODEL_INFO


def print_model_summary():
    """Print a summary of all models"""
    print("\n" + "="*60)
    print("SMART CAMPUS ATTENDANCE SYSTEM - DATABASE MODELS")
    print("="*60)
    
    for table_name, info in MODEL_INFO.items():
        print(f"\n📋 {table_name.upper()}")
        print(f"   Model: {info['model'].__name__}")
        print(f"   Description: {info['description']}")
        if 'roles' in info:
            print(f"   Roles: {', '.join(info['roles'])}")
        if 'related_to' in info:
            print(f"   Related: {', '.join(info['related_to'])}")
    
    print("\n" + "="*60)
    print(f"Total Models: {len(MODEL_INFO)}")
    print("="*60 + "\n")


# Run verification when module is imported
if __name__ == "__main__":
    verify_models_loaded()
    print_model_summary()