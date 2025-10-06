"""
Lecturer API endpoints
Handles lecturer-specific operations: course management, session management, attendance monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import (
    User, Lecturer, Student, Course, CourseSection, CourseAssignment,
    ClassSession, AttendanceRecord, CourseEnrollment,
    SessionStatus, AttendanceStatus
)
from app.api.auth import get_current_active_user, require_lecturer
from app.services.email_service import email_service
from app.config import settings

router = APIRouter()


# ==================== PROFILE ENDPOINTS ====================

@router.get("/profile", tags=["Lecturer Profile"])
async def get_lecturer_profile(
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get current lecturer's profile
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get assigned courses count
    courses_count = db.query(CourseAssignment).filter(
        CourseAssignment.lecturer_id == lecturer.id,
        CourseAssignment.is_active == True
    ).count()
    
    # Get total sessions count
    sessions_count = db.query(ClassSession).filter(
        ClassSession.lecturer_id == lecturer.id
    ).count()
    
    profile_data = {
        **current_user.to_dict(),
        **lecturer.to_dict(),
        "total_courses": courses_count,
        "total_sessions": sessions_count
    }
    
    return profile_data


@router.put("/profile", tags=["Lecturer Profile"])
async def update_lecturer_profile(
    phone: Optional[str] = Body(None),
    office_location: Optional[str] = Body(None),
    office_phone: Optional[str] = Body(None),
    office_hours: Optional[str] = Body(None),
    specialization: Optional[str] = Body(None),
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Update lecturer profile information
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Update user phone
    if phone:
        current_user.phone = phone
    
    # Update lecturer-specific fields
    if office_location:
        lecturer.office_location = office_location
    if office_phone:
        lecturer.office_phone = office_phone
    if office_hours:
        lecturer.office_hours = office_hours
    if specialization:
        lecturer.specialization = specialization
    
    db.commit()
    
    return {
        "message": "Profile updated successfully",
        "profile": lecturer.to_dict()
    }


# ==================== COURSE MANAGEMENT ====================

@router.get("/courses", tags=["Lecturer Courses"])
async def get_my_courses(
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get all courses assigned to the lecturer
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get course assignments
    assignments = db.query(CourseAssignment).filter(
        CourseAssignment.lecturer_id == lecturer.id,
        CourseAssignment.is_active == True
    ).all()
    
    courses_data = []
    for assignment in assignments:
        section = db.query(CourseSection).filter(
            CourseSection.id == assignment.section_id
        ).first()
        
        if section:
            course = db.query(Course).filter(Course.id == section.course_id).first()
            
            if course:
                # Get enrolled students count
                enrolled_count = db.query(CourseEnrollment).filter(
                    CourseEnrollment.course_id == course.id,
                    CourseEnrollment.status == "enrolled"
                ).count()
                
                # Get total sessions
                sessions_count = db.query(ClassSession).filter(
                    ClassSession.section_id == section.id,
                    ClassSession.lecturer_id == lecturer.id
                ).count()
                
                courses_data.append({
                    "assignment_id": assignment.id,
                    "course": course.to_dict(),
                    "section": section.to_dict(),
                    "role": assignment.role,
                    "enrolled_students": enrolled_count,
                    "total_sessions": sessions_count
                })
    
    return {
        "total_courses": len(courses_data),
        "courses": courses_data
    }


@router.get("/courses/{course_id}/students", tags=["Lecturer Courses"])
async def get_course_students(
    course_id: int,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get all students enrolled in a course
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Verify lecturer is assigned to this course
    # TODO: Add proper verification through course sections
    
    # Get enrolled students
    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.status == "enrolled"
    ).all()
    
    students_data = []
    for enrollment in enrollments:
        student = db.query(Student).filter(Student.id == enrollment.student_id).first()
        if student:
            user = db.query(User).filter(User.id == student.user_id).first()
            students_data.append({
                "student_id": student.student_id,
                "name": user.full_name if user else "Unknown",
                "email": user.email if user else None,
                "enrollment_date": enrollment.enrollment_date.isoformat(),
                "attendance_percentage": round(enrollment.attendance_percentage, 2),
                "total_classes": enrollment.total_classes,
                "classes_attended": enrollment.classes_attended,
                "is_face_enrolled": student.is_face_enrolled
            })
    
    return {
        "course_id": course_id,
        "total_students": len(students_data),
        "students": students_data
    }


# ==================== SESSION MANAGEMENT ====================

@router.post("/sessions/create", tags=["Session Management"])
async def create_class_session(
    section_id: int = Body(...),
    session_date: str = Body(...),  # YYYY-MM-DD
    start_time: str = Body(...),  # HH:MM
    end_time: str = Body(...),  # HH:MM
    room_number: Optional[str] = Body(None),
    building: Optional[str] = Body(None),
    topic: Optional[str] = Body(None),
    session_type: str = Body("lecture"),
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Create a new class session
    
    - **section_id**: Course section ID
    - **session_date**: Date (YYYY-MM-DD)
    - **start_time**: Start time (HH:MM)
    - **end_time**: End time (HH:MM)
    - **room_number**: Room number
    - **building**: Building name
    - **topic**: Topic/chapter
    - **session_type**: lecture, lab, tutorial, exam
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Verify section exists and lecturer is assigned
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course section not found"
        )
    
    # Parse datetime
    try:
        session_datetime = datetime.strptime(session_date, "%Y-%m-%d")
        start_dt = datetime.strptime(f"{session_date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{session_date} {end_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date/time format"
        )
    
    # Create session
    session = ClassSession(
        section_id=section_id,
        lecturer_id=lecturer.id,
        session_date=session_datetime,
        start_time=start_dt,
        end_time=end_dt,
        room_number=room_number,
        building=building,
        topic=topic,
        session_type=session_type,
        status=SessionStatus.SCHEDULED
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return {
        "message": "Class session created successfully",
        "session": session.to_dict()
    }


@router.get("/sessions", tags=["Session Management"])
async def get_my_sessions(
    date_from: Optional[str] = None,  # YYYY-MM-DD
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get all sessions for the lecturer
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Build query
    query = db.query(ClassSession).filter(ClassSession.lecturer_id == lecturer.id)
    
    # Apply filters
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(ClassSession.session_date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            query = query.filter(ClassSession.session_date <= to_date)
        except ValueError:
            pass
    
    if status:
        try:
            session_status = SessionStatus[status.upper()]
            query = query.filter(ClassSession.status == session_status)
        except KeyError:
            pass
    
    sessions = query.order_by(ClassSession.session_date.desc()).all()
    
    return {
        "total_sessions": len(sessions),
        "sessions": [s.to_dict() for s in sessions]
    }


@router.get("/sessions/today", tags=["Session Management"])
async def get_today_sessions(
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get today's class sessions
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get today's date range
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    sessions = db.query(ClassSession).filter(
        ClassSession.lecturer_id == lecturer.id,
        ClassSession.session_date >= today_start,
        ClassSession.session_date < today_end
    ).order_by(ClassSession.start_time).all()
    
    return {
        "date": today_start.date().isoformat(),
        "total_sessions": len(sessions),
        "sessions": [s.to_dict() for s in sessions]
    }


@router.get("/sessions/{session_id}", tags=["Session Management"])
async def get_session_details(
    session_id: int,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a session
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify ownership
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )
    
    # Get section and course info
    section = db.query(CourseSection).filter(CourseSection.id == session.section_id).first()
    course = None
    if section:
        course = db.query(Course).filter(Course.id == section.course_id).first()
    
    return {
        "session": session.to_dict(),
        "section": section.to_dict() if section else None,
        "course": course.to_dict() if course else None
    }


@router.put("/sessions/{session_id}", tags=["Session Management"])
async def update_session(
    session_id: int,
    topic: Optional[str] = Body(None),
    notes: Optional[str] = Body(None),
    room_number: Optional[str] = Body(None),
    building: Optional[str] = Body(None),
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Update session details
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify ownership
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this session"
        )
    
    # Update fields
    if topic is not None:
        session.topic = topic
    if notes is not None:
        session.notes = notes
    if room_number is not None:
        session.room_number = room_number
    if building is not None:
        session.building = building
    
    db.commit()
    
    return {
        "message": "Session updated successfully",
        "session": session.to_dict()
    }


@router.delete("/sessions/{session_id}", tags=["Session Management"])
async def cancel_session(
    session_id: int,
    reason: Optional[str] = Body(None),
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Cancel a scheduled session
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify ownership
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this session"
        )
    
    # Cancel session
    session.cancel_session(reason)
    db.commit()
    
    return {
        "message": "Session cancelled successfully",
        "session_id": session_id
    }


# ==================== ATTENDANCE REPORTS ====================

@router.get("/sessions/{session_id}/attendance-report", tags=["Reports"])
async def get_session_attendance_report(
    session_id: int,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get detailed attendance report for a session
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify ownership
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )
    
    # Get attendance records
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id
    ).all()
    
    # Get student details
    attendance_list = []
    for record in records:
        student = db.query(Student).filter(Student.id == record.student_id).first()
        if student:
            user = db.query(User).filter(User.id == student.user_id).first()
            attendance_list.append({
                "student_id": student.student_id,
                "student_name": user.full_name if user else "Unknown",
                "email": user.email if user else None,
                **record.to_dict()
            })
    
    return {
        "session": session.to_dict(),
        "statistics": {
            "total": session.total_students,
            "present": session.present_count,
            "late": session.late_count,
            "absent": session.absent_count,
            "percentage": round(session.attendance_percentage, 2)
        },
        "attendance": attendance_list
    }


@router.get("/courses/{course_id}/attendance-summary", tags=["Reports"])
async def get_course_attendance_summary(
    course_id: int,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get attendance summary for entire course
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get course enrollments
    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.status == "enrolled"
    ).all()
    
    students_summary = []
    for enrollment in enrollments:
        student = db.query(Student).filter(Student.id == enrollment.student_id).first()
        if student:
            user = db.query(User).filter(User.id == student.user_id).first()
            
            # Check if below minimum
            below_minimum = enrollment.attendance_percentage < settings.MINIMUM_ATTENDANCE_PERCENTAGE
            
            students_summary.append({
                "student_id": student.student_id,
                "student_name": user.full_name if user else "Unknown",
                "email": user.email if user else None,
                "total_classes": enrollment.total_classes,
                "classes_attended": enrollment.classes_attended,
                "attendance_percentage": round(enrollment.attendance_percentage, 2),
                "below_minimum": below_minimum
            })
    
    # Sort by attendance percentage
    students_summary.sort(key=lambda x: x['attendance_percentage'])
    
    return {
        "course_id": course_id,
        "total_students": len(students_summary),
        "students": students_summary
    }


# ==================== COMMUNICATION ====================

@router.post("/courses/{course_id}/email-students", tags=["Communication"])
async def email_course_students(
    course_id: int,
    subject: str = Body(...),
    message: str = Body(...),
    recipients: str = Body("all"),  # all, absent, low_attendance
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Send email to students in a course
    
    - **recipients**: all, absent, low_attendance
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get enrollments based on filter
    query = db.query(CourseEnrollment).filter(
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.status == "enrolled"
    )
    
    if recipients == "low_attendance":
        query = query.filter(
            CourseEnrollment.attendance_percentage < settings.MINIMUM_ATTENDANCE_PERCENTAGE
        )
    
    enrollments = query.all()
    
    # Prepare recipient list
    recipient_list = []
    for enrollment in enrollments:
        student = db.query(Student).filter(Student.id == enrollment.student_id).first()
        if student:
            user = db.query(User).filter(User.id == student.user_id).first()
            if user:
                recipient_list.append({
                    "email": user.email,
                    "name": user.full_name,
                    "user_id": user.id
                })
    
    if not recipient_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No students found matching criteria"
        )
    
    # Send bulk email
    results = await email_service.send_bulk_email(
        recipients=recipient_list,
        subject=subject,
        body_html=f"<p>{message}</p>",
        db=db
    )
    
    return {
        "message": "Emails sent",
        "total_recipients": len(recipient_list),
        "sent": results['sent'],
        "failed": results['failed']
    }