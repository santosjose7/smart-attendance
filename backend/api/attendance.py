"""
Attendance API endpoints
Handles attendance marking via face recognition and QR code
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import (
    User, Student, Lecturer, ClassSession, AttendanceRecord,
    CourseEnrollment, SessionStatus, AttendanceStatus, CheckInMethod
)
from app.api.auth import get_current_active_user, require_student, require_lecturer
from app.services.face_service import face_service
from app.utils.security import verify_qr_token, generate_qr_token
from app.config import settings

router = APIRouter()


# ==================== STUDENT CHECK-IN ENDPOINTS ====================

@router.post("/check-in/face", tags=["Attendance Check-in"])
async def check_in_with_face(
    session_id: int = Body(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Check-in to class using face recognition
    
    - **session_id**: Class session ID
    - **file**: Face photo
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Check if student has enrolled face
    if not student.is_face_enrolled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Face not enrolled. Please complete face enrollment first."
        )
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Check if session is active
    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is not active. Current status: {session.status.value}"
        )
    
    # Check if check-in window is open
    if not session.can_check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in window has closed"
        )
    
    # Check if already checked in
    existing_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.student_id == student.id
    ).first()
    
    if existing_record and existing_record.is_present:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already checked in to this session"
        )
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    # Read image
    image_data = await file.read()
    
    # Get enrolled students in this session's course (for optimization)
    # TODO: Get actual enrolled student IDs from course section
    
    # Recognize face
    success, recognized_student_id, confidence, message = face_service.recognize_face(
        image_data=image_data,
        candidate_student_ids=None,  # Check all students for now
        db=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Verify recognized student matches logged-in student
    if recognized_student_id != student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Face does not match enrolled student. Please try again or use QR code."
        )
    
    # Calculate if late
    check_in_time = datetime.utcnow()
    minutes_late = 0
    is_late = False
    
    if check_in_time > session.start_time:
        delta = check_in_time - session.start_time
        minutes_late = int(delta.total_seconds() / 60)
        is_late = minutes_late > settings.LATE_ARRIVAL_THRESHOLD
    
    # Create or update attendance record
    if existing_record:
        # Update existing record
        if is_late:
            existing_record.mark_late(minutes_late, CheckInMethod.FACE_RECOGNITION, check_in_time, confidence)
        else:
            existing_record.mark_present(CheckInMethod.FACE_RECOGNITION, check_in_time, confidence)
    else:
        # Create new record
        attendance_record = AttendanceRecord(
            session_id=session_id,
            student_id=student.id,
            status=AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT,
            check_in_method=CheckInMethod.FACE_RECOGNITION,
            check_in_time=check_in_time,
            minutes_late=minutes_late,
            is_late=is_late,
            face_confidence_score=confidence
        )
        db.add(attendance_record)
    
    # Update session statistics
    session.update_attendance_stats()
    
    # Update enrollment statistics
    # TODO: Update course enrollment total_classes and classes_attended
    
    db.commit()
    
    return {
        "message": "Attendance marked successfully",
        "status": "late" if is_late else "present",
        "check_in_time": check_in_time.isoformat(),
        "minutes_late": minutes_late,
        "confidence": round(confidence * 100, 1),
        "method": "face_recognition"
    }


@router.post("/check-in/qr", tags=["Attendance Check-in"])
async def check_in_with_qr(
    session_id: int = Body(...),
    qr_token: str = Body(...),
    latitude: Optional[float] = Body(None),
    longitude: Optional[float] = Body(None),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Check-in to class using QR code
    
    - **session_id**: Class session ID
    - **qr_token**: QR code token from lecturer's display
    - **latitude**: GPS latitude (optional)
    - **longitude**: GPS longitude (optional)
    """
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Check if session is active
    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is not active. Current status: {session.status.value}"
        )
    
    # Check if check-in window is open
    if not session.can_check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in window has closed"
        )
    
    # Verify QR token
    is_valid = verify_qr_token(
        token=qr_token,
        session_id=session_id,
        expiry_minutes=settings.QR_CODE_EXPIRY_MINUTES
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired QR code"
        )
    
    # Check if already checked in
    existing_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.student_id == student.id
    ).first()
    
    if existing_record and existing_record.is_present:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already checked in to this session"
        )
    
    # Calculate if late
    check_in_time = datetime.utcnow()
    minutes_late = 0
    is_late = False
    
    if check_in_time > session.start_time:
        delta = check_in_time - session.start_time
        minutes_late = int(delta.total_seconds() / 60)
        is_late = minutes_late > settings.LATE_ARRIVAL_THRESHOLD
    
    # Create or update attendance record
    if existing_record:
        # Update existing record
        if is_late:
            existing_record.mark_late(minutes_late, CheckInMethod.QR_CODE, check_in_time)
        else:
            existing_record.mark_present(CheckInMethod.QR_CODE, check_in_time)
        
        if latitude and longitude:
            existing_record.check_in_latitude = latitude
            existing_record.check_in_longitude = longitude
    else:
        # Create new record
        attendance_record = AttendanceRecord(
            session_id=session_id,
            student_id=student.id,
            status=AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT,
            check_in_method=CheckInMethod.QR_CODE,
            check_in_time=check_in_time,
            minutes_late=minutes_late,
            is_late=is_late,
            check_in_latitude=latitude,
            check_in_longitude=longitude
        )
        db.add(attendance_record)
    
    # Update session statistics
    session.update_attendance_stats()
    
    db.commit()
    
    return {
        "message": "Attendance marked successfully",
        "status": "late" if is_late else "present",
        "check_in_time": check_in_time.isoformat(),
        "minutes_late": minutes_late,
        "method": "qr_code"
    }


# ==================== LECTURER SESSION MANAGEMENT ====================

@router.post("/sessions/{session_id}/start", tags=["Session Management"])
async def start_session(
    session_id: int,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Start a class session (enables check-in)
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Verify lecturer owns this session
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this session"
        )
    
    # Check if already started
    if session.status == SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already in progress"
        )
    
    # Start session
    session.start_session(
        check_in_window_before=settings.ATTENDANCE_CHECK_IN_WINDOW_BEFORE,
        check_in_window_after=settings.ATTENDANCE_CHECK_IN_WINDOW_AFTER
    )
    
    # Generate QR code
    qr_token = session.generate_qr_code(expiry_minutes=settings.QR_CODE_EXPIRY_MINUTES)
    
    db.commit()
    
    return {
        "message": "Session started successfully",
        "session_id": session.id,
        "status": session.status.value,
        "check_in_window": {
            "start": session.check_in_started_at.isoformat(),
            "end": session.check_in_ended_at.isoformat()
        },
        "qr_code": qr_token
    }


@router.post("/sessions/{session_id}/end", tags=["Session Management"])
async def end_session(
    session_id: int,
    mark_absent: bool = Body(True),
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    End a class session (disables check-in)
    
    - **mark_absent**: Automatically mark non-checked-in students as absent
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Verify lecturer owns this session
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this session"
        )
    
    # Check if session is in progress
    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not in progress"
        )
    
    # Mark absent students if requested
    if mark_absent:
        # Get all enrolled students in this course/section
        # TODO: Get enrolled student IDs from course section
        
        # Get students who already have attendance records
        attended_student_ids = [
            r.student_id for r in db.query(AttendanceRecord).filter(
                AttendanceRecord.session_id == session_id
            ).all()
        ]
        
        # For now, skip auto-marking absent (need proper course enrollment query)
        # In production, mark all enrolled students not in attended_student_ids as absent
    
    # End session
    session.end_session()
    
    # Update statistics
    session.update_attendance_stats()
    
    db.commit()
    
    return {
        "message": "Session ended successfully",
        "session_id": session.id,
        "status": session.status.value,
        "attendance_stats": {
            "total_students": session.total_students,
            "present": session.present_count,
            "late": session.late_count,
            "absent": session.absent_count,
            "attendance_percentage": round(session.attendance_percentage, 2)
        }
    }


@router.get("/sessions/{session_id}/qr-code", tags=["Session Management"])
async def get_qr_code(
    session_id: int,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get QR code for active session
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Verify lecturer owns this session
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )
    
    # Check if session is active
    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active"
        )
    
    # Check if QR code is still valid
    if not session.is_qr_code_valid:
        # Generate new QR code
        qr_token = session.generate_qr_code(expiry_minutes=settings.QR_CODE_EXPIRY_MINUTES)
        db.commit()
    else:
        qr_token = session.qr_code_data
    
    return {
        "session_id": session.id,
        "qr_code": qr_token,
        "expires_at": session.qr_code_expires_at.isoformat(),
        "is_valid": session.is_qr_code_valid
    }


@router.post("/sessions/{session_id}/refresh-qr", tags=["Session Management"])
async def refresh_qr_code(
    session_id: int,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Refresh QR code (generate new token)
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Verify lecturer owns this session
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this session"
        )
    
    # Generate new QR code
    qr_token = session.generate_qr_code(expiry_minutes=settings.QR_CODE_EXPIRY_MINUTES)
    db.commit()
    
    return {
        "message": "QR code refreshed",
        "qr_code": qr_token,
        "expires_at": session.qr_code_expires_at.isoformat()
    }


# ==================== ATTENDANCE MONITORING ====================

@router.get("/sessions/{session_id}/live", tags=["Session Management"])
async def get_live_attendance(
    session_id: int,
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Get live attendance for active session
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Verify lecturer owns this session
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )
    
    # Get all attendance records for this session
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id
    ).order_by(AttendanceRecord.check_in_time.desc()).all()
    
    # Get student details
    attendance_list = []
    for record in records:
        student = db.query(Student).filter(Student.id == record.student_id).first()
        if student:
            user = db.query(User).filter(User.id == student.user_id).first()
            attendance_list.append({
                "student_id": student.student_id,
                "student_name": user.full_name if user else "Unknown",
                **record.to_dict()
            })
    
    return {
        "session_id": session.id,
        "status": session.status.value,
        "can_check_in": session.can_check_in,
        "statistics": {
            "total_students": session.total_students,
            "present": session.present_count,
            "late": session.late_count,
            "absent": session.absent_count,
            "percentage": round(session.attendance_percentage, 2)
        },
        "attendance": attendance_list
    }


# ==================== KIOSK MODE (NO LOGIN REQUIRED) ====================

@router.post("/sessions/{session_id}/kiosk/check-in", tags=["Kiosk Mode"])
async def kiosk_face_check_in(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Kiosk mode check-in - NO LOGIN REQUIRED
    Used at classroom entrance with a fixed camera/tablet
    Students just look at camera and get recognized automatically
    
    - **session_id**: Class session ID
    - **file**: Face photo from camera
    """
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Check if session is active
    if session.status != SessionStatus.IN_PROGRESS:
        return {
            "success": False,
            "message": f"Session is not active. Status: {session.status.value}",
            "show_qr_fallback": False
        }
    
    # Check if check-in window is open
    if not session.can_check_in:
        return {
            "success": False,
            "message": "Check-in window has closed",
            "show_qr_fallback": False
        }
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        return {
            "success": False,
            "message": "Invalid image file",
            "show_qr_fallback": True
        }
    
    # Read image
    image_data = await file.read()
    
    # Get all students enrolled in this session's course
    # TODO: Optimize by getting only enrolled student IDs
    # For now, search all students
    
    # Recognize face
    success, student_id, confidence, message = face_service.recognize_face(
        image_data=image_data,
        candidate_student_ids=None,  # Search all enrolled students
        db=db
    )
    
    if not success:
        return {
            "success": False,
            "message": message,
            "show_qr_fallback": True,
            "suggestion": "Please scan your student ID QR code"
        }
    
    # Get student details
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {
            "success": False,
            "message": "Student not found in database",
            "show_qr_fallback": True
        }
    
    user = db.query(User).filter(User.id == student.user_id).first()
    
    # Check if already checked in
    existing_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.student_id == student_id
    ).first()
    
    if existing_record and existing_record.is_present:
        return {
            "success": True,
            "already_checked_in": True,
            "student_name": user.full_name if user else "Unknown",
            "student_id": student.student_id,
            "message": "Already checked in",
            "previous_check_in": existing_record.check_in_time.isoformat(),
            "show_qr_fallback": False
        }
    
    # Calculate if late
    check_in_time = datetime.utcnow()
    minutes_late = 0
    is_late = False
    
    if check_in_time > session.start_time:
        delta = check_in_time - session.start_time
        minutes_late = int(delta.total_seconds() / 60)
        is_late = minutes_late > settings.LATE_ARRIVAL_THRESHOLD
    
    # Create or update attendance record
    if existing_record:
        if is_late:
            existing_record.mark_late(minutes_late, CheckInMethod.FACE_RECOGNITION, check_in_time, confidence)
        else:
            existing_record.mark_present(CheckInMethod.FACE_RECOGNITION, check_in_time, confidence)
    else:
        attendance_record = AttendanceRecord(
            session_id=session_id,
            student_id=student_id,
            status=AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT,
            check_in_method=CheckInMethod.FACE_RECOGNITION,
            check_in_time=check_in_time,
            minutes_late=minutes_late,
            is_late=is_late,
            face_confidence_score=confidence
        )
        db.add(attendance_record)
    
    # Update session statistics
    session.update_attendance_stats()
    
    db.commit()
    
    return {
        "success": True,
        "student_name": user.full_name if user else "Unknown",
        "student_id": student.student_id,
        "status": "late" if is_late else "present",
        "check_in_time": check_in_time.isoformat(),
        "minutes_late": minutes_late,
        "confidence": round(confidence * 100, 1),
        "message": f"Welcome, {user.first_name}!" if user else "Attendance marked",
        "show_qr_fallback": False
    }


@router.get("/sessions/{session_id}/kiosk/status", tags=["Kiosk Mode"])
async def get_kiosk_session_status(
    session_id: int,
    db: Session = Depends(get_db)
):
    """
    Get session status for kiosk display - NO LOGIN REQUIRED
    Shows if check-in is active and basic stats
    """
    
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    return {
        "session_id": session.id,
        "status": session.status.value,
        "can_check_in": session.can_check_in,
        "check_in_window": {
            "start": session.check_in_started_at.isoformat() if session.check_in_started_at else None,
            "end": session.check_in_ended_at.isoformat() if session.check_in_ended_at else None
        },
        "statistics": {
            "present": session.present_count,
            "late": session.late_count,
            "total": session.total_students
        }
    }


@router.post("/sessions/{session_id}/kiosk/qr-check-in", tags=["Kiosk Mode"])
async def kiosk_qr_check_in(
    session_id: int,
    student_id_number: str = Body(...),
    db: Session = Depends(get_db)
):
    """
    Kiosk mode QR check-in - NO LOGIN REQUIRED
    Student scans their student ID card QR code at kiosk
    
    - **session_id**: Class session ID
    - **student_id_number**: Student ID from QR code (e.g., "2021-CS-1234")
    """
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Check if session is active
    if session.status != SessionStatus.IN_PROGRESS:
        return {
            "success": False,
            "message": f"Session is not active. Status: {session.status.value}"
        }
    
    # Check if check-in window is open
    if not session.can_check_in:
        return {
            "success": False,
            "message": "Check-in window has closed"
        }
    
    # Find student by student ID number
    student = db.query(Student).filter(Student.student_id == student_id_number).first()
    
    if not student:
        return {
            "success": False,
            "message": "Student ID not found. Please contact lecturer.",
            "student_id": student_id_number
        }
    
    # Get user details
    user = db.query(User).filter(User.id == student.user_id).first()
    
    # Check if student is enrolled in this course
    # TODO: Add enrollment verification
    
    # Check if already checked in
    existing_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.student_id == student.id
    ).first()
    
    if existing_record and existing_record.is_present:
        return {
            "success": True,
            "already_checked_in": True,
            "student_name": user.full_name if user else "Unknown",
            "student_id": student.student_id,
            "message": "Already checked in",
            "previous_check_in": existing_record.check_in_time.isoformat()
        }
    
    # Calculate if late
    check_in_time = datetime.utcnow()
    minutes_late = 0
    is_late = False
    
    if check_in_time > session.start_time:
        delta = check_in_time - session.start_time
        minutes_late = int(delta.total_seconds() / 60)
        is_late = minutes_late > settings.LATE_ARRIVAL_THRESHOLD
    
    # Create or update attendance record
    if existing_record:
        if is_late:
            existing_record.mark_late(minutes_late, CheckInMethod.QR_CODE, check_in_time)
        else:
            existing_record.mark_present(CheckInMethod.QR_CODE, check_in_time)
    else:
        attendance_record = AttendanceRecord(
            session_id=session_id,
            student_id=student.id,
            status=AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT,
            check_in_method=CheckInMethod.QR_CODE,
            check_in_time=check_in_time,
            minutes_late=minutes_late,
            is_late=is_late
        )
        db.add(attendance_record)
    
    # Update session statistics
    session.update_attendance_stats()
    
    db.commit()
    
    return {
        "success": True,
        "student_name": user.full_name if user else "Unknown",
        "student_id": student.student_id,
        "status": "late" if is_late else "present",
        "check_in_time": check_in_time.isoformat(),
        "minutes_late": minutes_late,
        "message": f"Welcome, {user.first_name}!" if user else "Attendance marked",
        "method": "qr_code"
    }


# ==================== MANUAL ATTENDANCE OVERRIDE ====================

@router.post("/sessions/{session_id}/manual-mark", tags=["Manual Override"])
async def manual_mark_attendance(
    session_id: int,
    student_id: int = Body(...),
    status: str = Body(...),
    reason: Optional[str] = Body(None),
    current_user: User = Depends(require_lecturer),
    db: Session = Depends(get_db)
):
    """
    Manually mark student attendance
    
    - **student_id**: Student database ID
    - **status**: present, late, absent, excused
    - **reason**: Reason for manual marking
    """
    lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
    
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecturer profile not found"
        )
    
    # Validate status
    valid_statuses = ["present", "late", "absent", "excused"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    # Get session
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found"
        )
    
    # Verify lecturer owns this session
    if session.lecturer_id != lecturer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this session"
        )
    
    # Get student
    student = db.query(Student).filter(Student.id == student_id).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if record exists
    record = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.student_id == student_id
    ).first()
    
    # Convert string status to enum
    attendance_status = AttendanceStatus[status.upper()]
    
    if record:
        # Update existing record
        record.manual_override(attendance_status, lecturer.id, reason)
    else:
        # Create new record
        record = AttendanceRecord(
            session_id=session_id,
            student_id=student_id,
            status=attendance_status,
            check_in_method=CheckInMethod.MANUAL,
            manually_marked=True,
            marked_by_lecturer_id=lecturer.id,
            override_reason=reason
        )
        db.add(record)
    
    # Update session statistics
    session.update_attendance_stats()
    
    db.commit()
    
    return {
        "message": "Attendance marked manually",
        "record": record.to_dict()
    }