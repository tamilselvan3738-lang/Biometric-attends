from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.biometric.face_engine import FaceEngine
import numpy as np
import json

User = get_user_model()

class BiometricTestCase(TestCase):
    def setUp(self):
        self.engine = FaceEngine()
        # Create a mock 128x128 face template with random noise features
        np.random.seed(42) # Set seed for deterministic test assertions
        self.mock_face1 = np.random.randint(50, 200, (128, 128), dtype=np.uint8)
        self.mock_face2 = np.clip(self.mock_face1.astype(np.int16) + np.random.randint(-10, 10, (128, 128)), 0, 255).astype(np.uint8)
        self.mock_face3 = np.random.randint(50, 200, (128, 128), dtype=np.uint8)

    def test_compute_similarity(self):
        sim = self.engine.compute_similarity(self.mock_face1, self.mock_face2)
        # Identical or nearly constant value images correlate positively
        self.assertGreaterEqual(sim, 0.5)

    def test_invalid_face_fails(self):
        # Passing mock random strings should fail gracefully
        matched, msg = self.engine.verify_face("invalid_base64_data", self.mock_face1.tolist())
        self.assertFalse(matched)
