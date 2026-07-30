from django.db import models
from django.conf import settings

class CompanyProfile(models.Model):
    name = models.CharField(max_length=150)
    address = models.TextField()
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='company/', blank=True, null=True)

    def __str__(self):
        return self.name

class SystemSetting(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.key}: {self.value}"

class AdminLimit(models.Model):
    admin = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'ADMIN'}, related_name='limit')
    max_employees = models.IntegerField(default=5)

    def __str__(self):
        return f"{self.admin.username} Limit: {self.max_employees}"

class LimitRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='limit_requests')
    requested_limit = models.IntegerField()
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.admin.username} -> {self.requested_limit} ({self.status})"

class OrganizationProfile(models.Model):
    admin = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'ADMIN'}, related_name='organization')
    name = models.CharField(max_length=150)
    logo = models.ImageField(upload_to='organization_logos/', blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.name} (Admin: {self.admin.username})"

class TerminatedAccount(models.Model):
    username = models.CharField(max_length=150, unique=True)
    role = models.CharField(max_length=20)
    terminated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} ({self.role}) - Terminated"
