from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
import json
import base64
import numpy as np
import cv2
from apps.biometric.face_engine import FaceEngine
from apps.biometric.models import FaceEnrollment

User = get_user_model()

class FaceEngineQualityTestCase(TestCase):
    def setUp(self):
        self.engine = FaceEngine()
        # Generate a synthetic face-like gray image (128x128)
        self.valid_face_crop = np.ones((128, 128), dtype=np.uint8) * 128
        # Draw eyes
        cv2.circle(self.valid_face_crop, (40, 50), 10, 0, -1)
        cv2.circle(self.valid_face_crop, (88, 50), 10, 0, -1)
        # Draw nose
        cv2.rectangle(self.valid_face_crop, (60, 65), (68, 85), 50, -1)
        # Draw mouth
        cv2.rectangle(self.valid_face_crop, (45, 95), (83, 105), 30, -1)

    def test_validate_face_quality_normal(self):
        # Create a block with high-frequency edges but no eyes, centered and correct size
        plain_block = np.ones((128, 128), dtype=np.uint8) * 128
        for i in range(10):
            cv2.line(plain_block, (i*12, 0), (i*12, 128), 0, 1)
        bbox = (9, 9, 110, 110)
        ok, msg, score, checks = self.engine.validate_face_quality(plain_block, plain_block, bbox)
        self.assertFalse(ok)
        self.assertIn("Eyes are not visible", msg)

    def test_validate_face_quality_size(self):
        # Face occupies too little frame (centered but too small)
        bbox = (39, 39, 50, 50)
        ok, msg, score, checks = self.engine.validate_face_quality(self.valid_face_crop, self.valid_face_crop, bbox)
        self.assertFalse(ok)
        self.assertIn("Move closer", msg)

    def test_validate_face_quality_lighting_dark(self):
        # Centered and correct size, but too dark
        dark_face = np.ones((128, 128), dtype=np.uint8) * 10
        bbox = (9, 9, 110, 110)
        ok, msg, score, checks = self.engine.validate_face_quality(dark_face, dark_face, bbox)
        self.assertFalse(ok)
        self.assertIn("Too dark", msg)

    def test_validate_face_quality_lighting_bright(self):
        # Centered and correct size, but too bright
        bright_face = np.ones((128, 128), dtype=np.uint8) * 245
        bbox = (9, 9, 110, 110)
        ok, msg, score, checks = self.engine.validate_face_quality(bright_face, bright_face, bbox)
        self.assertFalse(ok)
        self.assertIn("Too bright", msg)

    def test_validate_face_quality_blur(self):
        # Blurry face (low Laplacian variance), centered and correct size
        blurry_face = np.ones((128, 128), dtype=np.uint8) * 128
        bbox = (9, 9, 110, 110)
        ok, msg, score, checks = self.engine.validate_face_quality(blurry_face, blurry_face, bbox)
        self.assertFalse(ok)
        self.assertIn("Avoid fast movement", msg)
