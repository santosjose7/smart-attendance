"""
Security utilities for the Smart Campus Attendance System
Handles password hashing, JWT tokens, and authentication
"""

from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
import re

from app.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==================== PASSWORD FUNCTIONS ====================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
    
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength based on requirements
    
    Args:
        password: Password to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    errors = []
    
    # Check minimum length
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long")
    
    # Check for uppercase letter
    if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    # Check for lowercase letter
    if settings.PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    # Check for digit
    if settings.PASSWORD_REQUIRE_DIGIT and not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    
    # Check for special character
    if settings.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")
    
    if errors:
        return False, "; ".join(errors)
    
    return True, "Password is strong"


def generate_random_password(length: int = 12) -> str:
    """
    Generate a random secure password
    
    Args:
        length: Length of password (minimum 12)
    
    Returns:
        Random password string
    """
    import string
    
    if length < 12:
        length = 12
    
    # Ensure password meets all requirements
    chars = string.ascii_letters + string.digits
    if settings.PASSWORD_REQUIRE_SPECIAL:
        chars += "!@#$%^&*"
    
    password = ''.join(secrets.choice(chars) for _ in range(length))
    
    # Ensure it meets requirements
    is_valid, _ = validate_password_strength(password)
    if not is_valid:
        # Try again recursively
        return generate_random_password(length)
    
    return password


# ==================== JWT TOKEN FUNCTIONS ====================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Data to encode in token (typically user_id and role)
        expires_delta: Custom expiration time
    
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token (longer expiry)
    
    Args:
        data: Data to encode in token
    
    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token
    
    Args:
        token: JWT token to verify
    
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without verification (use with caution)
    
    Args:
        token: JWT token to decode
    
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            options={"verify_signature": False}
        )
        return payload
    except JWTError:
        return None


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get expiration time from token
    
    Args:
        token: JWT token
    
    Returns:
        Expiration datetime or None
    """
    payload = decode_token(token)
    if payload and "exp" in payload:
        return datetime.fromtimestamp(payload["exp"])
    return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired
    
    Args:
        token: JWT token
    
    Returns:
        True if expired, False otherwise
    """
    expiry = get_token_expiry(token)
    if expiry:
        return datetime.utcnow() > expiry
    return True


# ==================== TOKEN GENERATION ====================

def generate_verification_token() -> str:
    """
    Generate a secure random token for email verification
    
    Returns:
        URL-safe token string
    """
    return secrets.token_urlsafe(32)


def generate_reset_token() -> str:
    """
    Generate a secure random token for password reset
    
    Returns:
        URL-safe token string
    """
    return secrets.token_urlsafe(32)


def generate_api_key() -> str:
    """
    Generate a secure API key
    
    Returns:
        API key string
    """
    return secrets.token_urlsafe(48)


# ==================== ENCRYPTION HELPERS ====================

def encrypt_data(data: str, key: Optional[str] = None) -> str:
    """
    Encrypt data using Fernet symmetric encryption
    
    Args:
        data: String data to encrypt
        key: Encryption key (uses SECRET_KEY if not provided)
    
    Returns:
        Encrypted data as string
    """
    from cryptography.fernet import Fernet
    import base64
    import hashlib
    
    # Use SECRET_KEY if no key provided
    if key is None:
        key = settings.SECRET_KEY
    
    # Create Fernet key from SECRET_KEY
    key_bytes = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    fernet = Fernet(fernet_key)
    
    # Encrypt
    encrypted = fernet.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted_data: str, key: Optional[str] = None) -> str:
    """
    Decrypt data using Fernet symmetric encryption
    
    Args:
        encrypted_data: Encrypted string
        key: Encryption key (uses SECRET_KEY if not provided)
    
    Returns:
        Decrypted data as string
    """
    from cryptography.fernet import Fernet
    import base64
    import hashlib
    
    # Use SECRET_KEY if no key provided
    if key is None:
        key = settings.SECRET_KEY
    
    # Create Fernet key from SECRET_KEY
    key_bytes = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    fernet = Fernet(fernet_key)
    
    # Decrypt
    decrypted = fernet.decrypt(encrypted_data.encode())
    return decrypted.decode()


# ==================== HASH FUNCTIONS ====================

def hash_string(data: str) -> str:
    """
    Create SHA-256 hash of a string
    
    Args:
        data: String to hash
    
    Returns:
        Hex digest of hash
    """
    import hashlib
    return hashlib.sha256(data.encode()).hexdigest()


def hash_file(file_path: str) -> str:
    """
    Create SHA-256 hash of a file
    
    Args:
        file_path: Path to file
    
    Returns:
        Hex digest of hash
    """
    import hashlib
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


# ==================== INPUT VALIDATION ====================

def validate_email(email: str) -> bool:
    """
    Validate email format
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent XSS
    
    Args:
        text: Input text
    
    Returns:
        Sanitized text
    """
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove script tags
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove event handlers
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def validate_phone_number(phone: str) -> bool:
    """
    Validate phone number format
    
    Args:
        phone: Phone number to validate
    
    Returns:
        True if valid, False otherwise
    """
    # Remove common separators
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it's a valid phone number (10-15 digits)
    pattern = r'^\+?[0-9]{10,15}$'
    return re.match(pattern, phone) is not None


# ==================== RATE LIMITING HELPERS ====================

def generate_rate_limit_key(identifier: str, endpoint: str) -> str:
    """
    Generate a rate limit key for caching
    
    Args:
        identifier: User ID or IP address
        endpoint: API endpoint
    
    Returns:
        Rate limit key
    """
    return f"rate_limit:{identifier}:{endpoint}"


# ==================== SECURITY HEADERS ====================

def get_security_headers() -> Dict[str, str]:
    """
    Get recommended security headers
    
    Returns:
        Dictionary of security headers
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
    }


# ==================== AUDIT LOGGING ====================

def log_security_event(event_type: str, user_id: Optional[int], details: str):
    """
    Log security-related events
    
    Args:
        event_type: Type of event (login_failed, password_reset, etc.)
        user_id: User ID involved (if applicable)
        details: Event details
    """
    import logging
    
    logger = logging.getLogger("security")
    logger.info(f"[{event_type}] User: {user_id} - {details}")


# ==================== UTILITY FUNCTIONS ====================

def generate_qr_token(session_id: int) -> str:
    """
    Generate secure token for QR code
    
    Args:
        session_id: Class session ID
    
    Returns:
        Encrypted QR token
    """
    timestamp = datetime.utcnow().isoformat()
    random_token = secrets.token_urlsafe(16)
    
    data = f"{session_id}:{timestamp}:{random_token}"
    return encrypt_data(data)


def verify_qr_token(token: str, session_id: int, expiry_minutes: int = 15) -> bool:
    """
    Verify QR code token
    
    Args:
        token: QR token to verify
        session_id: Expected session ID
        expiry_minutes: Token validity period
    
    Returns:
        True if valid, False otherwise
    """
    try:
        decrypted = decrypt_data(token)
        parts = decrypted.split(":")
        
        if len(parts) != 3:
            return False
        
        token_session_id, timestamp, _ = parts
        
        # Check session ID
        if int(token_session_id) != session_id:
            return False
        
        # Check expiry
        token_time = datetime.fromisoformat(timestamp)
        expiry_time = token_time + timedelta(minutes=expiry_minutes)
        
        return datetime.utcnow() <= expiry_time
        
    except Exception:
        return False


# Export main functions
__all__ = [
    # Password functions
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "generate_random_password",
    
    # JWT functions
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "decode_token",
    "get_token_expiry",
    "is_token_expired",
    
    # Token generation
    "generate_verification_token",
    "generate_reset_token",
    "generate_api_key",
    
    # Encryption
    "encrypt_data",
    "decrypt_data",
    
    # Hashing
    "hash_string",
    "hash_file",
    
    # Validation
    "validate_email",
    "sanitize_input",
    "validate_phone_number",
    
    # QR code
    "generate_qr_token",
    "verify_qr_token",
    
    # Utilities
    "get_security_headers",
    "log_security_event",
]