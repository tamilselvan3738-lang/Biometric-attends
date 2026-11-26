from django.db import models
from django.conf import settings
from apps.departments.models import Department

class EmployeeProfile(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employeeprofile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    designation = models.CharField(max_length=100)
    date_of_joining = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    EMPLOYEE_TYPE_CHOICES = (
        ('HR_TEAM', 'HR Team'),
        ('MANAGER', 'Manager'),
        ('EMPLOYEE', 'Employee'),
    )
    employee_type = models.CharField(max_length=20, choices=EMPLOYEE_TYPE_CHOICES, default='EMPLOYEE')
    reporting_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reportees')
    daily_salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    document = models.FileField(upload_to='employee_documents/', blank=True, null=True)
    profile_image = models.ImageField(upload_to='employee_profiles/', blank=True, null=True)
    failed_biometric_attempts = models.IntegerField(default=0)
    is_biometric_locked = models.BooleanField(default=False)
    biometric_lock_reason = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_employees', limit_choices_to={'role': 'ADMIN'})
    ot_hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    need_ot_check_in = models.BooleanField(default=True)
    shift = models.ForeignKey('attendance.Shift', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    custom_check_in_time = models.TimeField(null=True, blank=True)
    custom_check_out_time = models.TimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        old_need_ot = None
        if not is_new:
            try:
                old_need_ot = EmployeeProfile.objects.get(pk=self.pk).need_ot_check_in
            except Exception:
                pass
                
        super().save(*args, **kwargs)
        
        if is_new:
            from apps.employee_management.models import EmployeeOTSettingAuditLog
            creator_name = self.created_by.username if self.created_by else 'admin'
            EmployeeOTSettingAuditLog.objects.create(
                username=self.user.username,
                employee_type=self.employee_type,
                ot_permission_status='Yes' if self.need_ot_check_in else 'No',
                created_by=creator_name,
                modified_by=None
            )
        else:
            if old_need_ot is not None and old_need_ot != self.need_ot_check_in:
                from apps.employee_management.models import EmployeeOTSettingAuditLog
                modifier_name = getattr(self, 'modified_by_username', None) or (self.created_by.username if self.created_by else 'admin')
                EmployeeOTSettingAuditLog.objects.create(
                    username=self.user.username,
                    employee_type=self.employee_type,
                    ot_permission_status='Yes' if self.need_ot_check_in else 'No',
                    created_by=None,
                    modified_by=modifier_name
                )

    @property
    def display_employee_id(self):
        if '_' in self.employee_id:
            return self.employee_id.split('_', 1)[1]
        return self.employee_id

    @property
    def current_attendance_status(self):
        from apps.attendance.models import AttendanceRecord
        from apps.leave_management.models import LeaveRequest
        from django.utils import timezone
        
        today = timezone.localdate()
        # 1. Check if clocked in today
        record = AttendanceRecord.objects.filter(user=self.user, date=today).first()
        if record:
            return record.status  # 'PRESENT', 'LATE', etc.
            
        # 2. Check if on approved leave today
        leave = LeaveRequest.objects.filter(
            user=self.user,
            status='APPROVED',
            start_date__lte=today,
            end_date__gte=today
        ).exists()
        if leave:
            return 'ON_LEAVE'
            
        # 3. Check if it's weekend or custom holiday
        from apps.attendance.models import AdminAttendanceSettings
        try:
            settings_obj = AdminAttendanceSettings.objects.filter(admin=self.created_by).first()
            if settings_obj:
                is_off = (date_str in settings_obj.custom_holidays)
                if is_off:
                    return 'WEEKEND'
        except Exception:
            pass
            
        return 'ABSENT'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.display_username} - {self.display_employee_id}"

class EmployeeTimingAuditLog(models.Model):
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='timing_audit_logs')
    employee_id = models.CharField(max_length=50)
    employee_name = models.CharField(max_length=150)
    previous_check_in_time = models.TimeField(null=True, blank=True)
    previous_check_out_time = models.TimeField(null=True, blank=True)
    updated_check_in_time = models.TimeField(null=True, blank=True)
    updated_check_out_time = models.TimeField(null=True, blank=True)
    previous_ot_check_in_time = models.TimeField(null=True, blank=True)
    previous_ot_check_out_time = models.TimeField(null=True, blank=True)
    updated_ot_check_in_time = models.TimeField(null=True, blank=True)
    updated_ot_check_out_time = models.TimeField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='timing_updates')
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee_name} ({self.employee_id}) changed at {self.changed_at}"

class EmployeeShiftAuditLog(models.Model):
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='shift_audit_logs')
    employee_id = models.CharField(max_length=50)
    employee_name = models.CharField(max_length=150)
    previous_shift = models.ForeignKey('attendance.Shift', on_delete=models.SET_NULL, null=True, blank=True, related_name='previous_shift_audits')
    previous_shift_name = models.CharField(max_length=100)
    new_shift = models.ForeignKey('attendance.Shift', on_delete=models.SET_NULL, null=True, blank=True, related_name='new_shift_audits')
    new_shift_name = models.CharField(max_length=100)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='shift_updates')
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee_name} ({self.employee_id}) shift changed at {self.changed_at}"

class EmployeeOTSettingAuditLog(models.Model):
    username = models.CharField(max_length=150)
    employee_type = models.CharField(max_length=20)
    ot_permission_status = models.CharField(max_length=10)  # "Yes" or "No"
    created_by = models.CharField(max_length=150, blank=True, null=True)
    modified_by = models.CharField(max_length=150, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} ({self.employee_type}) - OT: {self.ot_permission_status} - Changed by: {self.modified_by or self.created_by}"
