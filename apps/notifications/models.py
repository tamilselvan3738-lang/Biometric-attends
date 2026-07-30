from django.db import models
from django.conf import settings

class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.username} - {self.title} - Read: {self.is_read}"

class Announcement(models.Model):
    ROLE_CHOICES = (
        ('ALL', 'All Users'),
        ('ADMINS', 'Administrators Only'),
        ('EMPLOYEES', 'Employees Only'),
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=150)
    content = models.TextField()
    target_role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='ALL')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Announcement: {self.title} (Target: {self.target_role})"
