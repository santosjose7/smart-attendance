"""
Admin API endpoints
Handles administrative operations: user management, course setup, system monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import csv
import io

from app.database import get_db, get_database_stats
from app.models import (
    User, Student, Lecturer, Course, CourseSection, CourseEnrollment,
    CourseAssignment, ClassSession, AttendanceRecord, EmailLog,
    UserRole, UserStatus, CourseStatus, EmailStatus
)
from app.api.auth import get_current_active_user, require_admin
from app.services.email_service import send_welcome_email, email_service
from app.utils.security import hash_password, generate_random_password
from app.config import settings

router = APIRouter()


# ==================== DASHBOARD & STATISTICS ====================

@router.get("/dashboard", tags=["Admin Dashboard"])
async def get_admin_dashboard(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get admin dashboard statistics
    """
    # Get database statistics
    db_stats = get_database_stats()
    
    # Get recent activity
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
    recent_sessions = db.query(ClassSession).order_by(
        ClassSession.created_at.desc()
    ).limit(5).all()
    
    # Get today's sessions
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    today_sessions = db.query(ClassSession).filter(
        ClassSession.session_date >= today_start,
        ClassSession.session_date < today_end
    ).count()
    
    # Get email statistics (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    emails_sent = db.query(EmailLog).filter(
        EmailLog.created_at >= week_ago,
        EmailLog.status.in_([EmailStatus.SENT, EmailStatus.DELIVERED])
    ).count()
    
    # Get low attendance students count
    low_attendance_count = db.query(CourseEnrollment).filter(
        CourseEnrollment.attendance_percentage < settings.MINIMUM_ATTENDANCE_PERCENTAGE,
        CourseEnrollment.status == "enrolled"
    ).count()
    
    return {
        "statistics": db_stats,
        "today_sessions": today_sessions,
        "emails_sent_7days": emails_sent,
        "low_attendance_students": low_attendance_count,
        "recent_users": [u.to_dict() for u in recent_users],
        "recent_sessions": [s.to_dict() for s in recent_sessions]
    }


@router.get("/system-health", tags=["Admin Dashboard"])
async def get_system_health(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get system health status
    """
    # Check face enrollment rate
    total_students = db.query(Student).count()
    enrolled_students = db.query(Student).filter(Student.is_face_enrolled == True).count()
    face_enrollment_rate = (enrolled_students / total_students * 100) if total_students > 0 else 0
    
    # Check email delivery rate
    total_emails = db.query(EmailLog).count()
    delivered_emails = db.query(EmailLog).filter(
        EmailLog.status.in_([EmailStatus.SENT, EmailStatus.DELIVERED])
    ).count()
    email_delivery_rate = (delivered_emails / total_emails * 100) if total_emails > 0 else 0
    
    # Check active sessions
    active_sessions = db.query(ClassSession).filter(
        ClassSession.status == "in_progress"
    ).count()
    
    return {
        "status": "healthy",
        "database_connected": True,
        "email_service_enabled": settings.EMAIL_ENABLED,
        "face_enrollment_rate": round(face_enrollment_rate, 2),
        "email_delivery_rate": round(email_delivery_rate, 2),
        "active_sessions": active_sessions,
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== USER MANAGEMENT ====================

@router.get("/users", tags=["User Management"])
async def get_all_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get all users with filters
    """
    query = db.query(User)
    
    # Apply filters
    if role:
        try:
            user_role = UserRole[role.upper()]
            query = query.filter(User.role == user_role)
        except KeyError:
            pass
    
    if status:
        try:
            user_status = UserStatus[status.upper()]
            query = query.filter(User.status == user_status)
        except KeyError:
            pass
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.first_name.ilike(search_term)) |
            (User.last_name.ilike(search_term)) |
            (User.email.ilike(search_term))
        )
    
    total = query.count()
    users = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "users": [u.to_dict() for u in users]
    }


@router.post("/users/create", tags=["User Management"])
async def create_user(
    email: str = Body(...),
    first_name: str = Body(...),
    last_name: str = Body(...),
    role: str = Body(...),  # admin, lecturer, student
    phone: Optional[str] = Body(None),
    department: Optional[str] = Body(None),
    send_welcome_email: bool = Body(True),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new user (admin, lecturer, or student)
    """
    # Validate role
    if role not in ["admin", "lecturer", "student"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'admin', 'lecturer', or 'student'"
        )
    
    # Check if email exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    # Generate random password
    temp_password = generate_random_password()
    
    # Create user
    user = User(
        email=email,
        password_hash=hash_password(temp_password),
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=UserRole[role.upper()],
        status=UserStatus.ACTIVE,
        is_email_verified=True  # Admin-created accounts are pre-verified
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create role-specific profile
    if role == "student":
        from app.models import create_student_id
        current_year = datetime.now().year
        student_count = db.query(Student).count()
        student_id = create_student_id(current_year, department or "GEN", student_count + 1)
        
        student = Student(
            user_id=user.id,
            student_id=student_id,
            enrollment_year=current_year,
            department=department
        )
        db.add(student)
        db.commit()
    
    elif role == "lecturer":
        from app.models import create_employee_id
        current_year = datetime.now().year
        lecturer_count = db.query(Lecturer).count()
        employee_id = create_employee_id(current_year, lecturer_count + 1)
        
        lecturer = Lecturer(
            user_id=user.id,
            employee_id=employee_id,
            department=department or "General"
        )
        db.add(lecturer)
        db.commit()
    
    # Send welcome email with temporary password
    if send_welcome_email:
        await send_welcome_email(
            to_email=user.email,
            to_name=user.full_name,
            user_id=user.id,
            role=role,
            db=db
        )
    
    return {
        "message": "User created successfully",
        "user": user.to_dict(),
        "temporary_password": temp_password,
        "note": "Please share this password securely with the user"
    }


@router.put("/users/{user_id}", tags=["User Management"])
async def update_user(
    user_id: int,
    first_name: Optional[str] = Body(None),
    last_name: Optional[str] = Body(None),
    phone: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update user information
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    if phone:
        user.phone = phone
    if status:
        try:
            user.status = UserStatus[status.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status"
            )
    
    db.commit()
    
    return {
        "message": "User updated successfully",
        "user": user.to_dict()
    }


@router.post("/users/{user_id}/reset-password", tags=["User Management"])
async def reset_user_password(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reset user password (generate new temporary password)
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate new password
    new_password = generate_random_password()
    user.password_hash = hash_password(new_password)
    
    db.commit()
    
    return {
        "message": "Password reset successfully",
        "temporary_password": new_password,
        "note": "Please share this password securely with the user"
    }


@router.delete("/users/{user_id}", tags=["User Management"])
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete (deactivate) a user
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Don't allow deleting yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete (deactivate)
    user.status = UserStatus.INACTIVE
    user.deleted_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "User deactivated successfully"
    }


# ==================== BULK IMPORT ====================

@router.post("/users/bulk-import", tags=["User Management"])
async def bulk_import_users(
    file: UploadFile = File(...),
    role: str = Body("student"),
    send_emails: bool = Body(False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Bulk import users from CSV file
    
    CSV Format:
    email,first_name,last_name,phone,department
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )
    
    # Read CSV
    content = await file.read()
    csv_file = io.StringIO(content.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)
    
    created_users = []
    errors = []
    
    for row_num, row in enumerate(csv_reader, start=2):
        try:
            email = row.get('email', '').strip()
            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            phone = row.get('phone', '').strip() or None
            department = row.get('department', '').strip() or None
            
            if not email or not first_name or not last_name:
                errors.append({
                    "row": row_num,
                    "error": "Missing required fields"
                })
                continue
            
            # Check if user exists
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                errors.append({
                    "row": row_num,
                    "email": email,
                    "error": "Email already exists"
                })
                continue
            
            # Generate password
            temp_password = generate_random_password()
            
            # Create user
            user = User(
                email=email,
                password_hash=hash_password(temp_password),
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=UserRole[role.upper()],
                status=UserStatus.ACTIVE,
                is_email_verified=True
            )
            
            db.add(user)
            db.flush()
            
            # Create role-specific profile
            if role == "student":
                from app.models import create_student_id
                current_year = datetime.now().year
                student_count = db.query(Student).count()
                student_id = create_student_id(current_year, department or "GEN", student_count + 1)
                
                student = Student(
                    user_id=user.id,
                    student_id=student_id,
                    enrollment_year=current_year,
                    department=department
                )
                db.add(student)
            
            elif role == "lecturer":
                from app.models import create_employee_id
                current_year = datetime.now().year
                lecturer_count = db.query(Lecturer).count()
                employee_id = create_employee_id(current_year, lecturer_count + 1)
                
                lecturer = Lecturer(
                    user_id=user.id,
                    employee_id=employee_id,
                    department=department or "General"
                )
                db.add(lecturer)
            
            created_users.append({
                "email": email,
                "name": f"{first_name} {last_name}",
                "password": temp_password
            })
            
            # Send welcome email
            if send_emails:
                await send_welcome_email(
                    to_email=user.email,
                    to_name=user.full_name,
                    user_id=user.id,
                    role=role,
                    db=db
                )
        
        except Exception as e:
            errors.append({
                "row": row_num,
                "error": str(e)
            })
    
    db.commit()
    
    return {
        "message": "Bulk import completed",
        "created": len(created_users),
        "failed": len(errors),
        "users": created_users,
        "errors": errors
    }


# ==================== COURSE MANAGEMENT ====================

@router.post("/courses/create", tags=["Course Management"])
async def create_course(
    course_code: str = Body(...),
    course_name: str = Body(...),
    department: str = Body(...),
    credit_hours: int = Body(...),
    semester: str = Body(...),
    academic_year: str = Body(...),
    description: Optional[str] = Body(None),
    max_capacity: Optional[int] = Body(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new course
    """
    # Check if course code exists
    existing = db.query(Course).filter(Course.course_code == course_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course code already exists"
        )
    
    course = Course(
        course_code=course_code,
        course_name=course_name,
        department=department,
        credit_hours=credit_hours,
        semester=semester,
        academic_year=academic_year,
        description=description,
        max_capacity=max_capacity,
        status=CourseStatus.ACTIVE
    )
    
    db.add(course)
    db.commit()
    db.refresh(course)
    
    return {
        "message": "Course created successfully",
        "course": course.to_dict()
    }


@router.post("/courses/{course_id}/sections", tags=["Course Management"])
async def create_course_section(
    course_id: int,
    section_name: str = Body(...),
    room_number: Optional[str] = Body(None),
    building: Optional[str] = Body(None),
    max_students: Optional[int] = Body(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a section for a course
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    section = CourseSection(
        course_id=course_id,
        section_name=section_name,
        section_code=f"{course.course_code}-{section_name}",
        room_number=room_number,
        building=building,
        max_students=max_students
    )
    
    db.add(section)
    db.commit()
    db.refresh(section)
    
    return {
        "message": "Section created successfully",
        "section": section.to_dict()
    }


@router.post("/courses/{course_id}/assign-lecturer", tags=["Course Management"])
async def assign_lecturer_to_course(
    course_id: int,
    lecturer_id: int = Body(...),
    section_id: int = Body(...),
    role: str = Body("primary"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Assign a lecturer to a course section
    """
    # Verify lecturer exists
    lecturer = db.query(Lecturer).filter(Lecturer.id == lecturer_id).first()
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer not found"
        )
    
    # Verify section exists
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section or section.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found"
        )
    
    # Check if already assigned
    existing = db.query(CourseAssignment).filter(
        CourseAssignment.lecturer_id == lecturer_id,
        CourseAssignment.section_id == section_id,
        CourseAssignment.is_active == True
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lecturer already assigned to this section"
        )
    
    # Create assignment
    assignment = CourseAssignment(
        lecturer_id=lecturer_id,
        section_id=section_id,
        role=role
    )
    
    db.add(assignment)
    db.commit()
    
    return {
        "message": "Lecturer assigned successfully",
        "assignment": assignment.to_dict()
    }


@router.post("/courses/{course_id}/enroll-student", tags=["Course Management"])
async def enroll_student_in_course(
    course_id: int,
    student_id: int = Body(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Enroll a student in a course
    """
    # Verify student exists
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Verify course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if already enrolled
    existing = db.query(CourseEnrollment).filter(
        CourseEnrollment.student_id == student_id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if existing and existing.status == "enrolled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student already enrolled in this course"
        )
    
    # Create enrollment
    enrollment = CourseEnrollment(
        student_id=student_id,
        course_id=course_id,
        status="enrolled"
    )
    
    db.add(enrollment)
    db.commit()
    
    return {
        "message": "Student enrolled successfully",
        "enrollment": enrollment.to_dict()
    }


# ==================== REPORTS ====================

@router.get("/reports/low-attendance", tags=["Reports"])
async def get_low_attendance_report(
    threshold: Optional[float] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get students with low attendance across all courses
    """
    if threshold is None:
        threshold = settings.MINIMUM_ATTENDANCE_PERCENTAGE
    
    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.attendance_percentage < threshold,
        CourseEnrollment.status == "enrolled"
    ).all()
    
    report_data = []
    for enrollment in enrollments:
        student = db.query(Student).filter(Student.id == enrollment.student_id).first()
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        
        if student and course:
            user = db.query(User).filter(User.id == student.user_id).first()
            report_data.append({
                "student_id": student.student_id,
                "student_name": user.full_name if user else "Unknown",
                "email": user.email if user else None,
                "course_code": course.course_code,
                "course_name": course.course_name,
                "attendance_percentage": round(enrollment.attendance_percentage, 2),
                "classes_attended": enrollment.classes_attended,
                "total_classes": enrollment.total_classes
            })
    
    return {
        "threshold": threshold,
        "total_students": len(report_data),
        "students": report_data
    }


@router.get("/reports/system-usage", tags=["Reports"])
async def get_system_usage_report(
    days: int = 30,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get system usage statistics
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Total sessions
    total_sessions = db.query(ClassSession).filter(
        ClassSession.created_at >= start_date
    ).count()
    
    # Total attendance records
    total_attendance = db.query(AttendanceRecord).filter(
        AttendanceRecord.created_at >= start_date
    ).count()
    
    # Face recognition vs QR code
    face_checkins = db.query(AttendanceRecord).filter(
        AttendanceRecord.created_at >= start_date,
        AttendanceRecord.check_in_method == "face_recognition"
    ).count()
    
    qr_checkins = db.query(AttendanceRecord).filter(
        AttendanceRecord.created_at >= start_date,
        AttendanceRecord.check_in_method == "qr_code"
    ).count()
    
    # Emails sent
    emails_sent = db.query(EmailLog).filter(
        EmailLog.created_at >= start_date
    ).count()
    
    return {
        "period_days": days,
        "total_sessions": total_sessions,
        "total_checkins": total_attendance,
        "face_recognition_checkins": face_checkins,
        "qr_code_checkins": qr_checkins,
        "emails_sent": emails_sent,
        "average_sessions_per_day": round(total_sessions / days, 2),
        "average_checkins_per_day": round(total_attendance / days, 2)
    }