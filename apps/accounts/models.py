from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('SUPER_ADMIN', 'Super Admin'),
        ('ADMIN', 'Admin'),
        ('EMPLOYEE', 'Employee'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='EMPLOYEE')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_approved = models.BooleanField(default=True)
    
    GENDER_CHOICES = (
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
    )
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='MALE')
    date_of_birth = models.DateField(blank=True, null=True)
    
    current_address = models.TextField(blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    
    is_terminated = models.BooleanField(default=False)
    terminated_at = models.DateTimeField(blank=True, null=True)
    terminated_by = models.ForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL, related_name='terminated_users')
    deletion_requested_at = models.DateTimeField(blank=True, null=True)
    permanently_deleted_at = models.DateTimeField(blank=True, null=True)

    @property
    def display_username(self):
        if self.role == 'EMPLOYEE' and '_' in self.username:
            return self.username.split('_', 1)[1]
        return self.username

    @property
    def get_organization_name(self):
        if self.role == 'ADMIN':
            try:
                return self.organization.name
            except Exception:
                return "BIO-ATTEND"
        elif self.role == 'EMPLOYEE':
            try:
                return self.employeeprofile.created_by.organization.name
            except Exception:
                return "BIO-ATTEND"
        return "BIO-ATTEND"

    @property
    def get_organization_logo_url(self):
        if self.role == 'ADMIN':
            try:
                if self.organization.logo:
                    return self.organization.logo.url
            except Exception:
                pass
        elif self.role == 'EMPLOYEE':
            try:
                if self.employeeprofile.created_by.organization.logo:
                    return self.employeeprofile.created_by.organization.logo.url
            except Exception:
                pass
        return None

    @property
    def is_ot_enabled(self):
        company_ot_enabled = False
        if self.role == 'ADMIN':
            try:
                company_ot_enabled = self.organization.enable_overtime
            except Exception:
                company_ot_enabled = True
        elif self.role == 'EMPLOYEE':
            try:
                company_ot_enabled = self.employeeprofile.created_by.organization.enable_overtime
            except Exception:
                company_ot_enabled = True
        else:
            company_ot_enabled = True
            
        if not company_ot_enabled:
            return False
            
        if self.role == 'EMPLOYEE':
            try:
                profile = self.employeeprofile
                # Check company-wide enable_employee_types setting
                enable_employee_types = profile.created_by.organization.enable_employee_types
                if not enable_employee_types:
                    return True
                
                if profile.employee_type == 'EMPLOYEE':
                    return True
                else:
                    return profile.need_ot_check_in
            except Exception:
                return True
        return True

    @property
    def enable_employee_types(self):
        if self.role == 'ADMIN':
            try:
                return self.organization.enable_employee_types
            except Exception:
                return True
        elif self.role == 'EMPLOYEE':
            try:
                return self.employeeprofile.created_by.organization.enable_employee_types
            except Exception:
                return True
        return True

    @property
    def is_manager(self):
        if not self.enable_employee_types:
            return False
        if self.role == 'EMPLOYEE':
            try:
                return self.employeeprofile.employee_type == 'MANAGER'
            except Exception:
                return False
        return False

    @property
    def is_hr(self):
        if not self.enable_employee_types:
            return False
        if self.role == 'EMPLOYEE':
            try:
                return self.employeeprofile.employee_type == 'HR_TEAM'
            except Exception:
                return False
        return False

    @property
    def is_regular_employee(self):
        if self.role == 'EMPLOYEE':
            try:
                if not self.enable_employee_types:
                    return True
                return self.employeeprofile.employee_type == 'EMPLOYEE'
            except Exception:
                return False
        return False

    def get_active_reportees(self):
        return self.reportees.filter(status='ACTIVE').select_related('user', 'department')

    def get_inactive_reportees(self):
        return self.reportees.filter(status='INACTIVE').select_related('user', 'department')

    def __str__(self):
        return f"{self.display_username} ({self.get_role_display()})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

class ForgotPasswordOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_otps')
    username = models.CharField(max_length=150)
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.username} - Code: {self.otp_code} - Verified: {self.is_verified}"
