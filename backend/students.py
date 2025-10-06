"""
Student API endpoints
Handles student-specific operations: face enrollment, attendance viewing, profile management
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import (
    User, Student, FaceEncoding, CourseEnrollment, AttendanceRecord,
    Course, ClassSession, AttendanceStatus
)
from app.api.auth import get_current_active_user, require_student
from app.services.face_service import face_service
from app.config import settings

router = APIRouter()


# ==================== PROFILE ENDPOINTS ====================

@router.get("/profile", tags=["Student Profile"])
async def get_student_profile(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get current student's profile
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get enrollment count
    enrollment_count = db.query(CourseEnrollment).filter(
        CourseEnrollment.student_id == student.id,
        CourseEnrollment.status == "enrolled"
    ).count()
    
    profile_data = {
        **current_user.to_dict(),
        **student.to_dict(),
        "total_courses": enrollment_count,
        "face_enrollment_complete": student.is_face_enrolled
    }
    
    return profile_data


@router.put("/profile", tags=["Student Profile"])
async def update_student_profile(
    phone: Optional[str] = Body(None),
    address: Optional[str] = Body(None),
    parent_name: Optional[str] = Body(None),
    parent_phone: Optional[str] = Body(None),
    parent_email: Optional[str] = Body(None),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Update student profile information
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Update user phone
    if phone:
        current_user.phone = phone
    
    # Update student-specific fields
    if address:
        student.address = address
    if parent_name:
        student.parent_name = parent_name
    if parent_phone:
        student.parent_phone = parent_phone
    if parent_email:
        student.parent_email = parent_email
    
    db.commit()
    
    return {
        "message": "Profile updated successfully",
        "profile": student.to_dict()
    }


# ==================== FACE ENROLLMENT ENDPOINTS ====================

@router.get("/face-enrollment/status", tags=["Face Enrollment"])
async def get_face_enrollment_status(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get face enrollment status and progress
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get enrollment progress
    progress = face_service.get_enrollment_progress(student.id, db)
    
    return {
        "student_id": student.student_id,
        "is_enrolled": student.is_face_enrolled,
        "enrollment_date": student.face_enrollment_date.isoformat() if student.face_enrollment_date else None,
        **progress
    }


@router.post("/face-enrollment/upload", tags=["Face Enrollment"])
async def upload_face_photo(
    file: UploadFile = File(...),
    angle: str = Body("front"),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Upload a face photo for enrollment
    
    - **file**: Image file (JPG, PNG)
    - **angle**: Capture angle (front, left, right, up, down)
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    # Validate angle
    valid_angles = ["front", "left", "right", "up", "down"]
    if angle not in valid_angles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid angle. Must be one of: {', '.join(valid_angles)}"
        )
    
    # Check if already at max photos
    existing_count = db.query(FaceEncoding).filter(
        FaceEncoding.student_id == student.id,
        FaceEncoding.is_active == True
    ).count()
    
    if existing_count >= settings.MAX_ENROLLMENT_PHOTOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.MAX_ENROLLMENT_PHOTOS} photos allowed"
        )
    
    # Read image data
    image_data = await file.read()
    
    # Validate image before enrollment
    is_valid, message, quality = face_service.validate_enrollment_image(image_data)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Enroll face
    success, encoding_record, enroll_message = face_service.enroll_student_face(
        student_id=student.id,
        image_data=image_data,
        capture_angle=angle,
        db=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=enroll_message
        )
    
    # Get updated progress
    progress = face_service.get_enrollment_progress(student.id, db)
    
    return {
        "message": enroll_message,
        "encoding_id": encoding_record.id,
        "quality_score": encoding_record.quality_score,
        "quality_grade": encoding_record.quality_grade,
        "progress": progress
    }


@router.get("/face-enrollment/photos", tags=["Face Enrollment"])
async def get_enrolled_photos(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get all enrolled face photos
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    encodings = db.query(FaceEncoding).filter(
        FaceEncoding.student_id == student.id,
        FaceEncoding.is_active == True
    ).order_by(FaceEncoding.created_at.desc()).all()
    
    return {
        "total": len(encodings),
        "photos": [e.to_dict() for e in encodings]
    }


@router.delete("/face-enrollment/photos/{encoding_id}", tags=["Face Enrollment"])
async def delete_face_photo(
    encoding_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Delete a specific face photo
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    encoding = db.query(FaceEncoding).filter(
        FaceEncoding.id == encoding_id,
        FaceEncoding.student_id == student.id
    ).first()
    
    if not encoding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found"
        )
    
    encoding.deactivate()
    db.commit()
    
    # Check if any photos remain
    remaining = db.query(FaceEncoding).filter(
        FaceEncoding.student_id == student.id,
        FaceEncoding.is_active == True
    ).count()
    
    if remaining == 0:
        student.is_face_enrolled = False
        student.face_enrollment_date = None
        db.commit()
    
    return {
        "message": "Photo deleted successfully",
        "remaining_photos": remaining
    }


@router.delete("/face-enrollment/reset", tags=["Face Enrollment"])
async def reset_face_enrollment(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Reset face enrollment (delete all photos)
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    success = face_service.delete_student_encodings(student.id, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset enrollment"
        )
    
    return {
        "message": "Face enrollment reset successfully"
    }


# ==================== COURSE ENROLLMENT ENDPOINTS ====================

@router.get("/courses", tags=["Student Courses"])
async def get_my_courses(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get all courses the student is enrolled in
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.student_id == student.id,
        CourseEnrollment.status == "enrolled"
    ).all()
    
    courses_data = []
    for enrollment in enrollments:
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        if course:
            courses_data.append({
                "enrollment_id": enrollment.id,
                "course": course.to_dict(),
                "enrollment_date": enrollment.enrollment_date.isoformat(),
                "total_classes": enrollment.total_classes,
                "classes_attended": enrollment.classes_attended,
                "attendance_percentage": round(enrollment.attendance_percentage, 2)
            })
    
    return {
        "total_courses": len(courses_data),
        "courses": courses_data
    }


@router.get("/courses/{course_id}/attendance", tags=["Student Courses"])
async def get_course_attendance(
    course_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get attendance records for a specific course
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Check if student is enrolled in this course
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.student_id == student.id,
        CourseEnrollment.course_id == course_id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not enrolled in this course"
        )
    
    # Get all attendance records for this course
    attendance_records = db.query(AttendanceRecord).join(
        ClassSession, AttendanceRecord.session_id == ClassSession.id
    ).join(
        Course, ClassSession.section_id == Course.id
    ).filter(
        AttendanceRecord.student_id == student.id,
        Course.id == course_id
    ).order_by(ClassSession.session_date.desc()).all()
    
    return {
        "course_id": course_id,
        "total_classes": enrollment.total_classes,
        "classes_attended": enrollment.classes_attended,
        "attendance_percentage": round(enrollment.attendance_percentage, 2),
        "records": [record.to_dict() for record in attendance_records]
    }


# ==================== ATTENDANCE SUMMARY ENDPOINTS ====================

@router.get("/attendance/summary", tags=["Student Attendance"])
async def get_attendance_summary(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get overall attendance summary across all courses
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get all enrollments
    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.student_id == student.id,
        CourseEnrollment.status == "enrolled"
    ).all()
    
    total_classes = sum(e.total_classes for e in enrollments)
    total_attended = sum(e.classes_attended for e in enrollments)
    overall_percentage = (total_attended / total_classes * 100) if total_classes > 0 else 0
    
    # Get recent attendance records
    recent_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student.id
    ).order_by(AttendanceRecord.marked_at.desc()).limit(10).all()
    
    # Count by status
    present_count = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student.id,
        AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE])
    ).count()
    
    absent_count = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student.id,
        AttendanceRecord.status == AttendanceStatus.ABSENT
    ).count()
    
    excused_count = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student.id,
        AttendanceRecord.status == AttendanceStatus.EXCUSED
    ).count()
    
    return {
        "overall_percentage": round(overall_percentage, 2),
        "total_classes": total_classes,
        "classes_attended": total_attended,
        "present_count": present_count,
        "absent_count": absent_count,
        "excused_count": excused_count,
        "courses_enrolled": len(enrollments),
        "recent_attendance": [r.to_dict() for r in recent_records],
        "meets_minimum": overall_percentage >= settings.MINIMUM_ATTENDANCE_PERCENTAGE
    }


@router.get("/attendance/today", tags=["Student Attendance"])
async def get_today_attendance(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get today's attendance records
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get today's date range
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Get attendance records for today
    records = db.query(AttendanceRecord).join(
        ClassSession, AttendanceRecord.session_id == ClassSession.id
    ).filter(
        AttendanceRecord.student_id == student.id,
        ClassSession.session_date >= today_start,
        ClassSession.session_date < today_end
    ).all()
    
    return {
        "date": today_start.date().isoformat(),
        "total_classes": len(records),
        "records": [r.to_dict() for r in records]
    }


@router.get("/attendance/history", tags=["Student Attendance"])
async def get_attendance_history(
    days: int = 30,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get attendance history for the last N days
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    records = db.query(AttendanceRecord).join(
        ClassSession, AttendanceRecord.session_id == ClassSession.id
    ).filter(
        AttendanceRecord.student_id == student.id,
        ClassSession.session_date >= start_date,
        ClassSession.session_date <= end_date
    ).order_by(ClassSession.session_date.desc()).all()
    
    return {
        "start_date": start_date.date().isoformat(),
        "end_date": end_date.date().isoformat(),
        "total_records": len(records),
        "records": [r.to_dict() for r in records]
    }


# ==================== SCHEDULE ENDPOINTS ====================

@router.get("/schedule/today", tags=["Student Schedule"])
async def get_today_schedule(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get today's class schedule
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get today's date range
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Get enrolled courses
    enrolled_course_ids = [
        e.course_id for e in db.query(CourseEnrollment).filter(
            CourseEnrollment.student_id == student.id,
            CourseEnrollment.status == "enrolled"
        ).all()
    ]
    
    if not enrolled_course_ids:
        return {"classes": []}
    
    # Get today's sessions for enrolled courses
    sessions = db.query(ClassSession).filter(
        ClassSession.session_date >= today_start,
        ClassSession.session_date < today_end,
        ClassSession.status != "cancelled"
    ).order_by(ClassSession.start_time).all()
    
    # Filter sessions for enrolled courses
    # Note: This would need proper join with course sections
    
    return {
        "date": today_start.date().isoformat(),
        "classes": [s.to_dict() for s in sessions]
    }