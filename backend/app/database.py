"""
Database configuration and session management
Handles SQLAlchemy setup and database connections
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import logging

from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
# The engine is the starting point for any SQLAlchemy application
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,  # Set to True to see SQL queries in console
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=10,  # Number of connections to keep open
    max_overflow=20,  # Additional connections that can be created on demand
    pool_recycle=3600,  # Recycle connections after 1 hour
)


# Create SessionLocal class
# Each instance of SessionLocal will be a database session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Create Base class for declarative models
# All models will inherit from this Base class
Base = declarative_base()


# Dependency to get database session
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session
    Usage in routes:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Database initialization functions
def init_db() -> None:
    """
    Initialize database by creating all tables
    Call this when starting the application
    """
    try:
        # Import all models here to ensure they are registered with Base
        from app.models import user, course, enrollment, session, attendance, face_encoding, email_log
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def drop_db() -> None:
    """
    Drop all database tables
    WARNING: This will delete all data!
    Use only in development
    """
    if not settings.DEBUG:
        raise Exception("Cannot drop database in production mode!")
    
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise


def reset_db() -> None:
    """
    Drop and recreate all tables
    WARNING: This will delete all data!
    Use only in development
    """
    if not settings.DEBUG:
        raise Exception("Cannot reset database in production mode!")
    
    drop_db()
    init_db()
    logger.warning("Database reset completed")


# Database health check
def check_db_connection() -> bool:
    """
    Check if database connection is working
    Returns True if connection is successful
    """
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


# Event listeners for database operations
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Enable foreign key support for SQLite (if using SQLite for testing)
    """
    cursor = dbapi_conn.cursor()
    if "sqlite" in settings.DATABASE_URL:
        cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@event.listens_for(engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    """
    Log slow queries (optional - for debugging)
    """
    if settings.DEBUG and settings.DATABASE_ECHO:
        logger.debug(f"Executing query: {statement}")


# Database utility functions
class DatabaseManager:
    """
    Utility class for common database operations
    """
    
    @staticmethod
    def create_all_tables():
        """Create all database tables"""
        init_db()
    
    @staticmethod
    def drop_all_tables():
        """Drop all database tables"""
        drop_db()
    
    @staticmethod
    def reset_database():
        """Reset database (drop and recreate)"""
        reset_db()
    
    @staticmethod
    def check_connection() -> bool:
        """Check database connection"""
        return check_db_connection()
    
    @staticmethod
    def get_session() -> Session:
        """Get a new database session"""
        return SessionLocal()
    
    @staticmethod
    def close_session(db: Session):
        """Close a database session"""
        db.close()


# Context manager for database sessions
class DatabaseSession:
    """
    Context manager for database sessions
    Usage:
        with DatabaseSession() as db:
            user = db.query(User).first()
    """
    
    def __init__(self):
        self.db = None
    
    def __enter__(self) -> Session:
        self.db = SessionLocal()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.db.rollback()
        self.db.close()


# Transaction decorator
def transactional(func):
    """
    Decorator for functions that need transaction management
    Automatically commits or rolls back based on success/failure
    """
    def wrapper(*args, **kwargs):
        db = kwargs.get('db') or args[0] if args else None
        if db is None or not isinstance(db, Session):
            raise ValueError("Database session not provided")
        
        try:
            result = func(*args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
    
    return wrapper


# Database statistics
def get_database_stats() -> dict:
    """
    Get database statistics (table counts, etc.)
    Useful for admin dashboard
    """
    try:
        with DatabaseSession() as db:
            # Import models
            from app.models.user import User
            from app.models.course import Course
            from app.models.attendance import AttendanceRecord
            from app.models.session import ClassSession
            
            stats = {
                "total_users": db.query(User).count(),
                "total_students": db.query(User).filter(User.role == "student").count(),
                "total_lecturers": db.query(User).filter(User.role == "lecturer").count(),
                "total_admins": db.query(User).filter(User.role == "admin").count(),
                "total_courses": db.query(Course).count(),
                "total_sessions": db.query(ClassSession).count(),
                "total_attendance_records": db.query(AttendanceRecord).count(),
            }
            return stats
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {}


# Export commonly used items
__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "init_db",
    "drop_db",
    "reset_db",
    "check_db_connection",
    "DatabaseManager",
    "DatabaseSession",
    "transactional",
    "get_database_stats"
]


# Startup message
if __name__ == "__main__":
    print("Database configuration loaded")
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"Connection status: {'✓ Connected' if check_db_connection() else '✗ Failed'}")