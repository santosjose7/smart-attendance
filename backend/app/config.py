"""
Configuration settings for Smart Campus Attendance System
Manages environment variables and application settings
"""

from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    
    # Application Settings
    APP_NAME: str = "Smart Campus Attendance System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:19006"]
    
    # Database Settings
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/attendance_db"
    DATABASE_ECHO: bool = False  # Set to True to see SQL queries
    
    # JWT Authentication Settings
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Email Settings (SendGrid or SMTP)
    EMAIL_ENABLED: bool = True
    EMAIL_FROM: str = "noreply@campus.edu"
    EMAIL_FROM_NAME: str = "Campus Attendance System"
    
    # SendGrid
    SENDGRID_API_KEY: Optional[str] = None
    
    # SMTP (Alternative to SendGrid)
    SMTP_HOST: Optional[str] = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True
    
    # Face Recognition Settings
    FACE_RECOGNITION_TOLERANCE: float = 0.6  # Lower = stricter matching
    FACE_ENCODING_MODEL: str = "large"  # 'small' or 'large'
    MIN_FACE_SIZE: int = 100  # Minimum face size in pixels
    MAX_ENROLLMENT_PHOTOS: int = 10
    MIN_ENROLLMENT_PHOTOS: int = 5
    
    # File Upload Settings
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_EXTENSIONS: list = [".jpg", ".jpeg", ".png"]
    
    # QR Code Settings
    QR_CODE_EXPIRY_MINUTES: int = 15
    QR_CODE_REFRESH_MINUTES: int = 5
    
    # Attendance Settings
    ATTENDANCE_CHECK_IN_WINDOW_BEFORE: int = 10  # Minutes before class
    ATTENDANCE_CHECK_IN_WINDOW_AFTER: int = 15   # Minutes after class starts
    LATE_ARRIVAL_THRESHOLD: int = 5  # Minutes after class starts
    MINIMUM_ATTENDANCE_PERCENTAGE: float = 75.0
    
    # Security Settings
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False
    
    # Session Settings
    MAX_CONCURRENT_SESSIONS: int = 3  # Per user
    SESSION_TIMEOUT_MINUTES: int = 60
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    
    # Redis (for caching and real-time features)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    CACHE_ENABLED: bool = False
    
    # WebSocket Settings
    WEBSOCKET_ENABLED: bool = True
    
    # Report Settings
    REPORT_OUTPUT_DIR: str = "./reports"
    REPORT_FORMATS: list = ["pdf", "excel"]
    
    # Notification Settings
    PUSH_NOTIFICATIONS_ENABLED: bool = True
    FIREBASE_CREDENTIALS_PATH: Optional[str] = "./firebase-credentials.json"
    
    # Academic Calendar
    SEMESTER_START_DATE: Optional[str] = None  # Format: YYYY-MM-DD
    SEMESTER_END_DATE: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Create and cache settings instance
    This ensures settings are loaded once and reused
    """
    return Settings()


# Create a global settings instance
settings = get_settings()


# Helper functions for specific configurations

def get_database_url() -> str:
    """Get database URL for SQLAlchemy"""
    return settings.DATABASE_URL


def get_cors_origins() -> list:
    """Get allowed CORS origins"""
    return settings.BACKEND_CORS_ORIGINS


def is_development() -> bool:
    """Check if running in development mode"""
    return settings.DEBUG


def is_production() -> bool:
    """Check if running in production mode"""
    return not settings.DEBUG


# Email configuration validator
def validate_email_config() -> bool:
    """
    Validate that email configuration is properly set
    Returns True if email can be sent
    """
    if not settings.EMAIL_ENABLED:
        return False
    
    # Check if either SendGrid or SMTP is configured
    has_sendgrid = settings.SENDGRID_API_KEY is not None
    has_smtp = (
        settings.SMTP_HOST is not None and 
        settings.SMTP_USER is not None and 
        settings.SMTP_PASSWORD is not None
    )
    
    return has_sendgrid or has_smtp


# Face recognition configuration
def get_face_recognition_config() -> dict:
    """Get face recognition configuration as dictionary"""
    return {
        "tolerance": settings.FACE_RECOGNITION_TOLERANCE,
        "model": settings.FACE_ENCODING_MODEL,
        "min_face_size": settings.MIN_FACE_SIZE,
        "max_photos": settings.MAX_ENROLLMENT_PHOTOS,
        "min_photos": settings.MIN_ENROLLMENT_PHOTOS
    }


# Attendance configuration
def get_attendance_config() -> dict:
    """Get attendance configuration as dictionary"""
    return {
        "check_in_before": settings.ATTENDANCE_CHECK_IN_WINDOW_BEFORE,
        "check_in_after": settings.ATTENDANCE_CHECK_IN_WINDOW_AFTER,
        "late_threshold": settings.LATE_ARRIVAL_THRESHOLD,
        "min_percentage": settings.MINIMUM_ATTENDANCE_PERCENTAGE
    }