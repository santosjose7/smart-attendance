"""
Main FastAPI application entry point
Smart Campus Attendance & Engagement System
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import time

from app.config import settings
from app.database import init_db, check_db_connection

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("Starting Smart Campus Attendance System...")
    
    # Check database connection
    logger.info("Checking database connection...")
    if check_db_connection():
        logger.info("✓ Database connection successful")
    else:
        logger.error("✗ Database connection failed!")
        raise Exception("Cannot connect to database")
    
    # Initialize database tables
    try:
        logger.info("Initializing database tables...")
        init_db()
        logger.info("✓ Database tables initialized")
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        raise
    
    # Verify models loaded
    from app.models import verify_models_loaded
    verify_models_loaded()
    
    logger.info("✓ Application startup complete")
    logger.info(f"Server running at http://{settings.HOST}:{settings.PORT}")
    logger.info(f"API documentation at http://{settings.HOST}:{settings.PORT}/docs")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Smart Campus Attendance System...")
    logger.info("✓ Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Automated attendance management system using face recognition and QR codes",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json"
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to responses"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - Status: {response.status_code}")
    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "message": "Smart Campus Attendance System API",
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": f"{settings.API_PREFIX}/docs",
        "endpoints": {
            "auth": f"{settings.API_PREFIX}/auth",
            "users": f"{settings.API_PREFIX}/users",
            "students": f"{settings.API_PREFIX}/students",
            "lecturers": f"{settings.API_PREFIX}/lecturers",
            "admin": f"{settings.API_PREFIX}/admin",
            "courses": f"{settings.API_PREFIX}/courses",
            "attendance": f"{settings.API_PREFIX}/attendance",
            "face_recognition": f"{settings.API_PREFIX}/face",
            "qr_code": f"{settings.API_PREFIX}/qr",
            "reports": f"{settings.API_PREFIX}/reports"
        }
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    db_status = check_db_connection()
    
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected",
        "version": settings.APP_VERSION,
        "environment": "development" if settings.DEBUG else "production"
    }


# API info endpoint
@app.get(f"{settings.API_PREFIX}/info", tags=["Info"])
async def api_info():
    """Get API information and statistics"""
    from app.database import get_database_stats
    
    try:
        db_stats = get_database_stats()
    except:
        db_stats = {}
    
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database_stats": db_stats,
        "features": {
            "face_recognition": True,
            "qr_code": True,
            "email_notifications": settings.EMAIL_ENABLED,
            "websockets": settings.WEBSOCKET_ENABLED,
            "push_notifications": settings.PUSH_NOTIFICATIONS_ENABLED
        },
        "settings": {
            "attendance_check_in_window_before": settings.ATTENDANCE_CHECK_IN_WINDOW_BEFORE,
            "attendance_check_in_window_after": settings.ATTENDANCE_CHECK_IN_WINDOW_AFTER,
            "late_arrival_threshold": settings.LATE_ARRIVAL_THRESHOLD,
            "minimum_attendance_percentage": settings.MINIMUM_ATTENDANCE_PERCENTAGE,
            "face_recognition_tolerance": settings.FACE_RECOGNITION_TOLERANCE,
            "qr_code_expiry_minutes": settings.QR_CODE_EXPIRY_MINUTES
        }
    }


# Import and include routers
# These will be created in subsequent files
"""
from app.api import auth, users, students, lecturers, admin
from app.api import courses, enrollment, attendance
from app.api import face_recognition, qr_code, reports

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_PREFIX}/users", tags=["Users"])
app.include_router(students.router, prefix=f"{settings.API_PREFIX}/students", tags=["Students"])
app.include_router(lecturers.router, prefix=f"{settings.API_PREFIX}/lecturers", tags=["Lecturers"])
app.include_router(admin.router, prefix=f"{settings.API_PREFIX}/admin", tags=["Admin"])
app.include_router(courses.router, prefix=f"{settings.API_PREFIX}/courses", tags=["Courses"])
app.include_router(enrollment.router, prefix=f"{settings.API_PREFIX}/enrollment", tags=["Enrollment"])
app.include_router(attendance.router, prefix=f"{settings.API_PREFIX}/attendance", tags=["Attendance"])
app.include_router(face_recognition.router, prefix=f"{settings.API_PREFIX}/face", tags=["Face Recognition"])
app.include_router(qr_code.router, prefix=f"{settings.API_PREFIX}/qr", tags=["QR Code"])
app.include_router(reports.router, prefix=f"{settings.API_PREFIX}/reports", tags=["Reports"])
"""


# Development-only endpoints
if settings.DEBUG:
    
    @app.get("/debug/config", tags=["Debug"])
    async def debug_config():
        """Get current configuration (debug only)"""
        return {
            "debug": settings.DEBUG,
            "database_url": settings.DATABASE_URL.replace(
                settings.DATABASE_URL.split('@')[0].split('//')[1],
                "****"
            ) if '@' in settings.DATABASE_URL else "****",
            "email_enabled": settings.EMAIL_ENABLED,
            "cors_origins": settings.BACKEND_CORS_ORIGINS,
        }
    
    @app.get("/debug/models", tags=["Debug"])
    async def debug_models():
        """Get information about all models (debug only)"""
        from app.models import MODEL_INFO
        return MODEL_INFO
    
    @app.post("/debug/reset-db", tags=["Debug"])
    async def debug_reset_database():
        """Reset database - WARNING: Deletes all data! (debug only)"""
        from app.database import reset_db
        try:
            reset_db()
            return {"message": "Database reset successful"}
        except Exception as e:
            return {"error": str(e)}


# WebSocket endpoint (if enabled)
if settings.WEBSOCKET_ENABLED:
    from fastapi import WebSocket, WebSocketDisconnect
    
    class ConnectionManager:
        """Manage WebSocket connections"""
        def __init__(self):
            self.active_connections: list[WebSocket] = []
        
        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
        
        def disconnect(self, websocket: WebSocket):
            self.active_connections.remove(websocket)
        
        async def broadcast(self, message: dict):
            for connection in self.active_connections:
                await connection.send_json(message)
    
    manager = ConnectionManager()
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates"""
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                await manager.broadcast({"message": data})
        except WebSocketDisconnect:
            manager.disconnect(websocket)


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )