"""
Authentication API endpoints
Handles user login, registration, password reset, email verification
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import secrets

from app.database import get_db
from app.config import settings
from app.models import User, Student, Lecturer, UserRole, UserStatus
# from app.utils.security import verify_password, hash_password, create_access_token, verify_token
from app.services.email_service import  send_welcome_email, send_verification_email, send_password_reset_email

# from app.schemas.auth import UserRegister, UserLogin, TokenResponse, PasswordReset

router = APIRouter()

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


# Temporary password functions (will be moved to utils/security.py)
def hash_password(password: str) -> str:
    """Hash password - placeholder"""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password - placeholder"""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token - placeholder"""
    from jose import jwt
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify JWT token - placeholder"""
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


# Dependency to get current user from token
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: int = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    return user


# Dependency to require active user
async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require user to be active"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return current_user


# Dependency to require specific role
def require_role(required_role: UserRole):
    """Factory function to create role dependency"""
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role.value}"
            )
        return current_user
    return role_checker


# Dependency to require admin
require_admin = require_role(UserRole.ADMIN)

# Dependency to require lecturer
require_lecturer = require_role(UserRole.LECTURER)

# Dependency to require student
require_student = require_role(UserRole.STUDENT)


# ==================== AUTHENTICATION ENDPOINTS ====================

@router.post("/register", status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def register(
    email: str = Body(...),
    password: str = Body(...),
    first_name: str = Body(...),
    last_name: str = Body(...),
    role: str = Body(...),  # "student" or "lecturer"
    phone: Optional[str] = Body(None),
    db: Session = Depends(get_db)
):
    """
    Register a new user account
    
    - **email**: Valid email address
    - **password**: Strong password (min 8 characters)
    - **first_name**: First name
    - **last_name**: Last name
    - **role**: User role (student or lecturer)
    - **phone**: Phone number (optional)
    """
    
    # Validate role
    if role not in ["student", "lecturer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'student' or 'lecturer'"
        )
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate password strength
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters"
        )
    
    # Create user
    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=UserRole.STUDENT if role == "student" else UserRole.LECTURER,
        status=UserStatus.PENDING,
        email_verification_token=secrets.token_urlsafe(32)
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create role-specific profile
    if role == "student":
        # Generate student ID
        from app.models import create_student_id
        current_year = datetime.now().year
        # Get count of existing students for sequence
        student_count = db.query(Student).count()
        student_id = create_student_id(current_year, "GEN", student_count + 1)
        
        student = Student(
            user_id=user.id,
            student_id=student_id,
            enrollment_year=current_year
        )
        db.add(student)
        db.commit()
    
    elif role == "lecturer":
        # Generate employee ID
        from app.models import create_employee_id
        current_year = datetime.now().year
        lecturer_count = db.query(Lecturer).count()
        employee_id = create_employee_id(current_year, lecturer_count + 1)
        
        lecturer = Lecturer(
            user_id=user.id,
            employee_id=employee_id,
            department="General"
        )
        db.add(lecturer)
        db.commit()
    
    # Send verification email (placeholder)
    # await send_verification_email(user.email, user.email_verification_token)
    
    return {
        "message": "Registration successful. Please check your email to verify your account.",
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value
    }


@router.post("/login", tags=["Authentication"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login to get access token
    
    - **username**: Email address
    - **password**: Password
    """
    
    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active. Please contact administrator."
        )
    
    # Check if email is verified
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your email for verification link."
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    user.failed_login_attempts = 0
    db.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


@router.get("/me", tags=["Authentication"])
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user information
    """
    user_data = current_user.to_dict()
    
    # Add role-specific data
    if current_user.is_student:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            user_data["student_profile"] = student.to_dict()
    
    elif current_user.is_lecturer:
        lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id).first()
        if lecturer:
            user_data["lecturer_profile"] = lecturer.to_dict()
    
    return user_data


@router.post("/verify-email", tags=["Authentication"])
async def verify_email(
    token: str = Body(...),
    db: Session = Depends(get_db)
):
    """
    Verify email address with token
    
    - **token**: Verification token from email
    """
    
    user = db.query(User).filter(User.email_verification_token == token).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    
    # Mark email as verified
    user.is_email_verified = True
    user.email_verification_token = None
    user.status = UserStatus.ACTIVE
    db.commit()
    
    return {
        "message": "Email verified successfully. You can now login."
    }


@router.post("/forgot-password", tags=["Authentication"])
async def forgot_password(
    email: str = Body(...),
    db: Session = Depends(get_db)
):
    """
    Request password reset
    
    - **email**: Email address
    """
    
    user = db.query(User).filter(User.email == email).first()
    
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If the email exists, a password reset link has been sent."}
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    user.password_reset_token = reset_token
    user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    
    # Send password reset email (placeholder)
    # await send_password_reset_email(user.email, reset_token)
    
    return {
        "message": "If the email exists, a password reset link has been sent."
    }


@router.post("/reset-password", tags=["Authentication"])
async def reset_password(
    token: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(get_db)
):
    """
    Reset password with token
    
    - **token**: Reset token from email
    - **new_password**: New password
    """
    
    user = db.query(User).filter(User.password_reset_token == token).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )
    
    # Check if token expired
    if user.password_reset_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )
    
    # Validate new password
    if len(new_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters"
        )
    
    # Update password
    user.password_hash = hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()
    
    return {
        "message": "Password reset successful. You can now login with your new password."
    }


@router.post("/logout", tags=["Authentication"])
async def logout(
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout (client should delete token)
    """
    return {
        "message": "Logged out successfully"
    }


@router.post("/change-password", tags=["Authentication"])
async def change_password(
    current_password: str = Body(...),
    new_password: str = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change password for authenticated user
    
    - **current_password**: Current password
    - **new_password**: New password
    """
    
    # Verify current password
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Validate new password
    if len(new_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters"
        )
    
    # Check if new password is same as current
    if verify_password(new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Update password
    current_user.password_hash = hash_password(new_password)
    db.commit()
    
    return {
        "message": "Password changed successfully"
    }


@router.get("/check-email", tags=["Authentication"])
async def check_email_availability(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Check if email is available for registration
    
    - **email**: Email to check
    """
    
    user = db.query(User).filter(User.email == email).first()
    
    return {
        "email": email,
        "available": user is None
    }