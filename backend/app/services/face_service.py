"""
Face Recognition Service
Handles face detection, encoding, and recognition for attendance
"""

import face_recognition
import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
from datetime import datetime
import logging
from PIL import Image
import io

from app.config import settings
from app.models import FaceEncoding, Student
from app.models.face_encoding import (
    serialize_encoding,
    deserialize_encoding,
    calculate_encoding_distance,
    calculate_quality_score
)

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """
    Service for face detection, encoding, and recognition
    """
    
    def __init__(self):
        self.tolerance = settings.FACE_RECOGNITION_TOLERANCE
        self.model = settings.FACE_ENCODING_MODEL
        self.min_face_size = settings.MIN_FACE_SIZE
    
    
    def detect_face(self, image_data: bytes) -> Tuple[bool, Optional[np.ndarray], Optional[Dict]]:
        """
        Detect face in image
        
        Args:
            image_data: Image bytes
        
        Returns:
            Tuple of (success, face_location, metadata)
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return False, None, {"error": "Invalid image"}
            
            # Convert BGR to RGB (OpenCV uses BGR, face_recognition uses RGB)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Detect faces
            face_locations = face_recognition.face_locations(rgb_image, model="hog")
            
            if len(face_locations) == 0:
                return False, None, {"error": "No face detected"}
            
            if len(face_locations) > 1:
                return False, None, {"error": "Multiple faces detected. Please ensure only one face in image"}
            
            # Get face location
            top, right, bottom, left = face_locations[0]
            
            # Calculate face size
            face_width = right - left
            face_height = bottom - top
            face_size = min(face_width, face_height)
            
            # Check minimum face size
            if face_size < self.min_face_size:
                return False, None, {
                    "error": f"Face too small. Minimum size: {self.min_face_size}px, detected: {face_size}px"
                }
            
            metadata = {
                "face_location": face_locations[0],
                "face_size": face_size,
                "image_width": image.shape[1],
                "image_height": image.shape[0]
            }
            
            return True, rgb_image, metadata
            
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return False, None, {"error": str(e)}
    
    
    def generate_encoding(self, image_data: bytes) -> Tuple[bool, Optional[np.ndarray], Optional[Dict]]:
        """
        Generate face encoding from image
        
        Args:
            image_data: Image bytes
        
        Returns:
            Tuple of (success, encoding, metadata)
        """
        try:
            # Detect face first
            success, rgb_image, metadata = self.detect_face(image_data)
            
            if not success:
                return False, None, metadata
            
            # Generate face encoding
            face_encodings = face_recognition.face_encodings(
                rgb_image,
                known_face_locations=[metadata["face_location"]],
                model=self.model
            )
            
            if len(face_encodings) == 0:
                return False, None, {"error": "Could not generate face encoding"}
            
            encoding = face_encodings[0]
            
            # Detect facial landmarks
            face_landmarks = face_recognition.face_landmarks(
                rgb_image,
                face_locations=[metadata["face_location"]]
            )
            
            landmarks_count = len(face_landmarks[0]) if face_landmarks else 0
            
            # Check if key facial features are detected
            eyes_detected = False
            nose_detected = False
            mouth_detected = False
            
            if face_landmarks:
                landmarks = face_landmarks[0]
                eyes_detected = 'left_eye' in landmarks and 'right_eye' in landmarks
                nose_detected = 'nose_tip' in landmarks
                mouth_detected = 'top_lip' in landmarks and 'bottom_lip' in landmarks
            
            metadata.update({
                "encoding_generated": True,
                "landmarks_count": landmarks_count,
                "eyes_detected": eyes_detected,
                "nose_detected": nose_detected,
                "mouth_detected": mouth_detected
            })
            
            return True, encoding, metadata
            
        except Exception as e:
            logger.error(f"Encoding generation error: {e}")
            return False, None, {"error": str(e)}
    
    
    def assess_image_quality(self, image_data: bytes) -> Dict:
        """
        Assess image quality for face recognition
        
        Args:
            image_data: Image bytes
        
        Returns:
            Dictionary with quality metrics
        """
        try:
            # Convert to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return {"error": "Invalid image"}
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Calculate brightness (average pixel intensity)
            brightness = np.mean(gray) / 255.0
            
            # Calculate sharpness (Laplacian variance)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = laplacian.var() / 1000.0  # Normalize
            sharpness = min(sharpness, 1.0)  # Cap at 1.0
            
            # Get face size if face detected
            success, _, face_metadata = self.detect_face(image_data)
            face_size = face_metadata.get("face_size", 0) if success else 0
            
            return {
                "brightness": round(brightness, 2),
                "sharpness": round(sharpness, 2),
                "face_size": face_size,
                "is_good_lighting": 0.3 <= brightness <= 0.8,
                "is_sharp": sharpness >= 0.6,
                "is_good_quality": success and 0.3 <= brightness <= 0.8 and sharpness >= 0.6
            }
            
        except Exception as e:
            logger.error(f"Quality assessment error: {e}")
            return {"error": str(e)}
    
    
    def enroll_student_face(
        self,
        student_id: int,
        image_data: bytes,
        capture_angle: str = "front",
        db = None
    ) -> Tuple[bool, Optional[FaceEncoding], str]:
        """
        Enroll a student's face (save encoding to database)
        
        Args:
            student_id: Student ID
            image_data: Image bytes
            capture_angle: Angle of capture (front, left, right, up, down)
            db: Database session
        
        Returns:
            Tuple of (success, face_encoding_record, message)
        """
        try:
            # Generate encoding
            success, encoding, metadata = self.generate_encoding(image_data)
            
            if not success:
                return False, None, metadata.get("error", "Failed to generate encoding")
            
            # Assess quality
            quality_metrics = self.assess_image_quality(image_data)
            
            # Calculate overall quality score
            quality_score = calculate_quality_score(
                face_size=metadata.get("face_size", 0),
                brightness=quality_metrics.get("brightness", 0.5),
                sharpness=quality_metrics.get("sharpness", 0.5),
                features_detected=metadata.get("eyes_detected", False) and 
                                metadata.get("nose_detected", False) and 
                                metadata.get("mouth_detected", False)
            )
            
            # Check if student already has this encoding (duplicate check)
            if db:
                existing_encodings = db.query(FaceEncoding).filter(
                    FaceEncoding.student_id == student_id,
                    FaceEncoding.is_active == True
                ).all()
                
                # Check for duplicates
                serialized_encoding = serialize_encoding(encoding)
                for existing in existing_encodings:
                    distance = calculate_encoding_distance(serialized_encoding, existing.encoding)
                    if distance < 0.3:  # Very similar
                        return False, None, "This photo appears to be a duplicate or very similar to an existing photo"
            
            # Create face encoding record
            face_encoding_record = FaceEncoding(
                student_id=student_id,
                encoding=serialize_encoding(encoding),
                quality_score=quality_score,
                face_size=metadata.get("face_size"),
                brightness_score=quality_metrics.get("brightness"),
                sharpness_score=quality_metrics.get("sharpness"),
                capture_angle=capture_angle,
                eyes_detected=metadata.get("eyes_detected", False),
                nose_detected=metadata.get("nose_detected", False),
                mouth_detected=metadata.get("mouth_detected", False),
                face_landmarks_count=metadata.get("landmarks_count", 0),
                is_active=True
            )
            
            # Save to database
            if db:
                db.add(face_encoding_record)
                db.commit()
                db.refresh(face_encoding_record)
                
                # Check if this is the first or best quality encoding
                student_encodings = db.query(FaceEncoding).filter(
                    FaceEncoding.student_id == student_id,
                    FaceEncoding.is_active == True
                ).all()
                
                if len(student_encodings) == 1 or quality_score > 0.8:
                    # Mark as primary if first encoding or high quality
                    face_encoding_record.mark_as_primary()
                    db.commit()
                
                # Update student face enrollment status
                student = db.query(Student).filter(Student.id == student_id).first()
                if student and not student.is_face_enrolled:
                    student.is_face_enrolled = True
                    student.face_enrollment_date = datetime.utcnow()
                    db.commit()
            
            message = f"Face enrolled successfully. Quality: {face_encoding_record.quality_grade}"
            return True, face_encoding_record, message
            
        except Exception as e:
            logger.error(f"Face enrollment error: {e}")
            if db:
                db.rollback()
            return False, None, str(e)
    
    
    def recognize_face(
        self,
        image_data: bytes,
        candidate_student_ids: List[int] = None,
        db = None
    ) -> Tuple[bool, Optional[int], Optional[float], str]:
        """
        Recognize a face from image against enrolled students
        
        Args:
            image_data: Image bytes
            candidate_student_ids: List of student IDs to check against (None = all)
            db: Database session
        
        Returns:
            Tuple of (success, student_id, confidence, message)
        """
        try:
            # Generate encoding from input image
            success, encoding, metadata = self.generate_encoding(image_data)
            
            if not success:
                return False, None, None, metadata.get("error", "Failed to detect face")
            
            if not db:
                return False, None, None, "Database session required"
            
            # Get candidate encodings from database
            query = db.query(FaceEncoding).filter(FaceEncoding.is_active == True)
            
            if candidate_student_ids:
                query = query.filter(FaceEncoding.student_id.in_(candidate_student_ids))
            
            stored_encodings = query.all()
            
            if not stored_encodings:
                return False, None, None, "No enrolled students found"
            
            # Compare against all stored encodings
            serialized_input = serialize_encoding(encoding)
            best_match_id = None
            best_distance = float('inf')
            best_encoding_record = None
            
            for stored in stored_encodings:
                distance = calculate_encoding_distance(serialized_input, stored.encoding)
                
                if distance < best_distance:
                    best_distance = distance
                    best_match_id = stored.student_id
                    best_encoding_record = stored
            
            # Check if match is within tolerance
            if best_distance <= self.tolerance:
                # Calculate confidence (0-1 scale)
                confidence = 1.0 - (best_distance / self.tolerance)
                
                # Update match statistics
                if best_encoding_record:
                    best_encoding_record.update_match_stats(confidence)
                    db.commit()
                
                return True, best_match_id, confidence, "Face recognized"
            else:
                return False, None, None, "Face not recognized. Please use QR code or contact lecturer."
            
        except Exception as e:
            logger.error(f"Face recognition error: {e}")
            return False, None, None, str(e)
    
    
    def get_enrollment_progress(self, student_id: int, db) -> Dict:
        """
        Get student's face enrollment progress
        
        Args:
            student_id: Student ID
            db: Database session
        
        Returns:
            Dictionary with enrollment progress
        """
        encodings = db.query(FaceEncoding).filter(
            FaceEncoding.student_id == student_id,
            FaceEncoding.is_active == True
        ).all()
        
        required_angles = ["front", "left", "right", "up", "down"]
        captured_angles = [e.capture_angle for e in encodings if e.capture_angle]
        
        return {
            "total_photos": len(encodings),
            "required_photos": settings.MIN_ENROLLMENT_PHOTOS,
            "is_complete": len(encodings) >= settings.MIN_ENROLLMENT_PHOTOS,
            "captured_angles": captured_angles,
            "missing_angles": [a for a in required_angles if a not in captured_angles],
            "average_quality": np.mean([e.quality_score for e in encodings if e.quality_score]) if encodings else 0,
            "has_primary": any(e.is_primary for e in encodings)
        }
    
    
    def delete_student_encodings(self, student_id: int, db) -> bool:
        """
        Delete all face encodings for a student (soft delete)
        
        Args:
            student_id: Student ID
            db: Database session
        
        Returns:
            Success status
        """
        try:
            encodings = db.query(FaceEncoding).filter(
                FaceEncoding.student_id == student_id
            ).all()
            
            for encoding in encodings:
                encoding.deactivate()
            
            # Update student status
            student = db.query(Student).filter(Student.id == student_id).first()
            if student:
                student.is_face_enrolled = False
                student.face_enrollment_date = None
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Delete encodings error: {e}")
            db.rollback()
            return False
    
    
    def validate_enrollment_image(self, image_data: bytes) -> Tuple[bool, str, Dict]:
        """
        Validate image before enrollment
        
        Args:
            image_data: Image bytes
        
        Returns:
            Tuple of (is_valid, message, details)
        """
        # Check face detection
        success, _, metadata = self.detect_face(image_data)
        
        if not success:
            return False, metadata.get("error", "Invalid image"), {}
        
        # Check quality
        quality = self.assess_image_quality(image_data)
        
        issues = []
        
        if not quality.get("is_good_lighting"):
            brightness = quality.get("brightness", 0)
            if brightness < 0.3:
                issues.append("Image too dark. Please improve lighting.")
            elif brightness > 0.8:
                issues.append("Image too bright. Reduce lighting.")
        
        if not quality.get("is_sharp"):
            issues.append("Image is blurry. Please ensure camera is focused.")
        
        if metadata.get("face_size", 0) < self.min_face_size * 1.5:
            issues.append("Face too small. Please move closer to camera.")
        
        if issues:
            return False, " ".join(issues), quality
        
        return True, "Image is good quality", quality


# Create singleton instance
face_service = FaceRecognitionService()


# Export main functions
__all__ = [
    "FaceRecognitionService",
    "face_service"
]