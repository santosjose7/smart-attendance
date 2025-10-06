"""
Face Encoding model for the Smart Campus Attendance System
Stores facial recognition data for students
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, LargeBinary, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class FaceEncoding(Base):
    """
    Face Encoding model
    Stores the 128-dimensional facial embeddings for face recognition
    Each student can have multiple face encodings (5-10 photos from different angles)
    """
    __tablename__ = "face_encodings"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    
    # Face Encoding Data
    # The 128-dimensional face embedding stored as binary data
    encoding = Column(LargeBinary, nullable=False)  # Serialized numpy array
    
    # Photo Information
    photo_url = Column(String(500), nullable=True)  # Optional: store original photo
    photo_hash = Column(String(64), nullable=True)  # SHA-256 hash for duplicate detection
    
    # Quality Metrics
    quality_score = Column(Float, nullable=True)  # Overall quality score (0-1)
    face_size = Column(Integer, nullable=True)  # Face size in pixels
    brightness_score = Column(Float, nullable=True)  # Lighting quality (0-1)
    sharpness_score = Column(Float, nullable=True)  # Focus quality (0-1)
    
    # Capture Details
    capture_angle = Column(String(20), nullable=True)  # front, left, right, up, down
    capture_device = Column(String(100), nullable=True)  # Device used (web, mobile)
    capture_method = Column(String(50), nullable=True)  # enrollment, update
    
    # Facial Features Detected
    eyes_detected = Column(Boolean, default=True)
    nose_detected = Column(Boolean, default=True)
    mouth_detected = Column(Boolean, default=True)
    face_landmarks_count = Column(Integer, nullable=True)  # Number of landmarks detected
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_primary = Column(Boolean, default=False)  # Mark best quality as primary
    
    # Verification
    is_verified = Column(Boolean, default=False)  # Manual verification by admin
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # Usage Statistics
    match_count = Column(Integer, default=0)  # How many times this encoding matched
    last_matched_at = Column(DateTime, nullable=True)
    average_confidence = Column(Float, nullable=True)  # Average confidence when matched
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    
    # Relationships
    student = relationship("Student", back_populates="face_encodings")
    
    def __repr__(self):
        return f"<FaceEncoding(id={self.id}, student_id={self.student_id}, quality={self.quality_score})>"
    
    @property
    def is_high_quality(self) -> bool:
        """Check if encoding is high quality"""
        if self.quality_score:
            return self.quality_score >= 0.7
        return False
    
    @property
    def is_good_lighting(self) -> bool:
        """Check if lighting was good during capture"""
        if self.brightness_score:
            return 0.3 <= self.brightness_score <= 0.8
        return False
    
    @property
    def is_sharp(self) -> bool:
        """Check if image was sharp (not blurry)"""
        if self.sharpness_score:
            return self.sharpness_score >= 0.6
        return False
    
    @property
    def all_features_detected(self) -> bool:
        """Check if all facial features were detected"""
        return self.eyes_detected and self.nose_detected and self.mouth_detected
    
    @property
    def quality_grade(self) -> str:
        """Get quality grade (A, B, C, D, F)"""
        if not self.quality_score:
            return "N/A"
        
        if self.quality_score >= 0.9:
            return "A"
        elif self.quality_score >= 0.8:
            return "B"
        elif self.quality_score >= 0.7:
            return "C"
        elif self.quality_score >= 0.6:
            return "D"
        else:
            return "F"
    
    def update_match_stats(self, confidence: float):
        """
        Update statistics after a successful match
        
        Args:
            confidence: Confidence score of the match (0-1)
        """
        self.match_count += 1
        self.last_matched_at = datetime.utcnow()
        
        # Calculate running average of confidence
        if self.average_confidence:
            self.average_confidence = (
                (self.average_confidence * (self.match_count - 1) + confidence) 
                / self.match_count
            )
        else:
            self.average_confidence = confidence
    
    def mark_as_primary(self):
        """Mark this encoding as the primary one for the student"""
        self.is_primary = True
    
    def deactivate(self):
        """Deactivate this encoding (soft delete)"""
        self.is_active = False
        self.deleted_at = datetime.utcnow()
    
    def verify(self, verified_by_user_id: int):
        """
        Mark encoding as verified by admin
        
        Args:
            verified_by_user_id: User ID of admin who verified
        """
        self.is_verified = True
        self.verified_by = verified_by_user_id
        self.verified_at = datetime.utcnow()
    
    def to_dict(self, include_encoding: bool = False) -> dict:
        """
        Convert face encoding to dictionary
        
        Args:
            include_encoding: Whether to include the actual encoding data
        """
        data = {
            "id": self.id,
            "student_id": self.student_id,
            "photo_url": self.photo_url,
            "quality_score": round(self.quality_score, 2) if self.quality_score else None,
            "quality_grade": self.quality_grade,
            "face_size": self.face_size,
            "brightness_score": round(self.brightness_score, 2) if self.brightness_score else None,
            "sharpness_score": round(self.sharpness_score, 2) if self.sharpness_score else None,
            "capture_angle": self.capture_angle,
            "is_active": self.is_active,
            "is_primary": self.is_primary,
            "is_verified": self.is_verified,
            "match_count": self.match_count,
            "average_confidence": round(self.average_confidence, 2) if self.average_confidence else None,
            "created_at": self.created_at.isoformat(),
        }
        
        if include_encoding and self.encoding:
            # Note: encoding would need to be decoded from binary
            data["encoding"] = "binary_data"
        
        return data


# Helper functions for face encoding management
def serialize_encoding(encoding_array) -> bytes:
    """
    Serialize numpy array to bytes for storage
    
    Args:
        encoding_array: 128-dimensional numpy array
    
    Returns:
        Binary data
    """
    import numpy as np
    import pickle
    
    return pickle.dumps(encoding_array)


def deserialize_encoding(encoding_bytes: bytes):
    """
    Deserialize bytes to numpy array
    
    Args:
        encoding_bytes: Binary encoding data
    
    Returns:
        128-dimensional numpy array
    """
    import pickle
    
    return pickle.loads(encoding_bytes)


def calculate_encoding_distance(encoding1_bytes: bytes, encoding2_bytes: bytes) -> float:
    """
    Calculate Euclidean distance between two face encodings
    
    Args:
        encoding1_bytes: First encoding (binary)
        encoding2_bytes: Second encoding (binary)
    
    Returns:
        Distance (lower = more similar)
    """
    import numpy as np
    
    enc1 = deserialize_encoding(encoding1_bytes)
    enc2 = deserialize_encoding(encoding2_bytes)
    
    return np.linalg.norm(enc1 - enc2)


def is_same_face(encoding1_bytes: bytes, encoding2_bytes: bytes, 
                 tolerance: float = 0.6) -> bool:
    """
    Check if two encodings represent the same face
    
    Args:
        encoding1_bytes: First encoding (binary)
        encoding2_bytes: Second encoding (binary)
        tolerance: Maximum distance to consider a match
    
    Returns:
        True if same face, False otherwise
    """
    distance = calculate_encoding_distance(encoding1_bytes, encoding2_bytes)
    return distance <= tolerance


def find_best_match(target_encoding: bytes, candidate_encodings: list, 
                    tolerance: float = 0.6) -> tuple:
    """
    Find the best matching encoding from a list of candidates
    
    Args:
        target_encoding: The encoding to match
        candidate_encodings: List of (id, encoding_bytes) tuples
        tolerance: Maximum distance to consider a match
    
    Returns:
        Tuple of (encoding_id, distance, confidence) or (None, None, None) if no match
    """
    if not candidate_encodings:
        return None, None, None
    
    best_id = None
    best_distance = float('inf')
    
    for encoding_id, encoding_bytes in candidate_encodings:
        distance = calculate_encoding_distance(target_encoding, encoding_bytes)
        
        if distance < best_distance and distance <= tolerance:
            best_distance = distance
            best_id = encoding_id
    
    if best_id is not None:
        # Convert distance to confidence score (0-1)
        confidence = 1 - (best_distance / tolerance)
        return best_id, best_distance, confidence
    
    return None, None, None


def calculate_quality_score(face_size: int, brightness: float, sharpness: float,
                           features_detected: bool) -> float:
    """
    Calculate overall quality score for a face encoding
    
    Args:
        face_size: Face size in pixels
        brightness: Brightness score (0-1)
        sharpness: Sharpness score (0-1)
        features_detected: All features detected
    
    Returns:
        Quality score (0-1)
    """
    scores = []
    
    # Face size score (larger is better, up to 300px)
    size_score = min(face_size / 300, 1.0) if face_size else 0.5
    scores.append(size_score * 0.3)  # 30% weight
    
    # Brightness score (optimal range 0.3-0.8)
    if brightness:
        if 0.3 <= brightness <= 0.8:
            brightness_score = 1.0
        elif brightness < 0.3:
            brightness_score = brightness / 0.3
        else:
            brightness_score = 1.0 - ((brightness - 0.8) / 0.2)
        scores.append(brightness_score * 0.25)  # 25% weight
    
    # Sharpness score
    if sharpness:
        scores.append(sharpness * 0.25)  # 25% weight
    
    # Features detected
    features_score = 1.0 if features_detected else 0.5
    scores.append(features_score * 0.2)  # 20% weight
    
    return sum(scores)


def select_best_encodings(encodings: list, max_count: int = 5) -> list:
    """
    Select the best quality encodings from a list
    
    Args:
        encodings: List of FaceEncoding objects
        max_count: Maximum number to select
    
    Returns:
        List of best encodings
    """
    # Sort by quality score (descending)
    sorted_encodings = sorted(
        [e for e in encodings if e.is_active],
        key=lambda x: x.quality_score or 0,
        reverse=True
    )
    
    return sorted_encodings[:max_count]


def check_duplicate_photo(photo_hash: str, student_id: int) -> bool:
    """
    Check if a photo hash already exists for a student
    
    Args:
        photo_hash: SHA-256 hash of the photo
        student_id: Student ID
    
    Returns:
        True if duplicate found
    """
    # This would be implemented in a service layer with database access
    pass


def get_encoding_statistics(student_id: int) -> dict:
    """
    Get statistics about a student's face encodings
    
    Args:
        student_id: Student ID
    
    Returns:
        Dictionary with encoding statistics
    """
    return {
        "total_encodings": 0,
        "active_encodings": 0,
        "verified_encodings": 0,
        "average_quality": 0.0,
        "primary_encoding_id": None,
        "total_matches": 0,
        "last_matched": None
    }