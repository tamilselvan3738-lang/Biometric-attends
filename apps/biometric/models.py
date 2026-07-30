from django.db import models
from django.conf import settings

class FaceEnrollment(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='faceenrollment')
    face_data = models.TextField() # Serialized JSON array of normalized face features
    enrolled_image = models.ImageField(upload_to='face_enrollments/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Face enrollment for {self.user.username}"

    @property
    def face_embedding(self):
        """
        Returns the computed average embedding (mean histogram) from all enrolled templates.
        """
        import json
        import numpy as np
        from apps.biometric.face_engine import FaceEngine
        try:
            data = json.loads(self.face_data)
            templates = data.get('templates', [])
            if not templates:
                return []
            engine = FaceEngine()
            histograms = []
            for t in templates:
                arr = np.array(t, dtype=np.uint8).reshape(128, 128)
                h = engine.get_gabor_arcface_embedding(arr)
                histograms.append(h)
            avg_hist = np.mean(histograms, axis=0)
            return avg_hist.tolist()
        except Exception:
            return []

class BiometricLog(models.Model):
    ACTION_CHOICES = (
        ('ENROLL', 'Face Enrollment'),
        ('VERIFY', 'Face Verification'),
        ('DELETE', 'Enrollment Deletion'),
    )
    STATUS_CHOICES = (
        ('SUCCESS', 'Success'),
        ('FAILURE', 'Failure'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='biometric_logs')
    action = models.CharField(max_length=15, choices=ACTION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    details = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.status}"
