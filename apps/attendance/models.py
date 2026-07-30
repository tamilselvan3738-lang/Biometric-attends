from django.db import models
from django.conf import settings
from django.utils import timezone

class AttendanceRecord(models.Model):
    STATUS_CHOICES = (
        ('PRESENT', 'Present'),
        ('LATE', 'Late'),
        ('HALF_DAY', 'Half Day'),
        ('ABSENT', 'Absent'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.localdate)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)
    check_in_image = models.ImageField(upload_to='attendance_captures/checkin/', null=True, blank=True)
    check_out_image = models.ImageField(upload_to='attendance_captures/checkout/', null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PRESENT')
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_early_checkout = models.BooleanField(default=False)
    lateness_minutes = models.IntegerField(default=0)
    early_checkout_minutes = models.IntegerField(default=0)
    similarity_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    # Shift snapshot fields
    shift = models.ForeignKey('Shift', on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_records')
    shift_name = models.CharField(max_length=50, blank=True, null=True)
    shift_start_time = models.TimeField(blank=True, null=True)
    shift_end_time = models.TimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date', '-check_in']
        unique_together = ('user', 'date')

    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.status}"

    @property
    def dynamic_lateness_minutes(self):
        if self.shift_start_time:
            shift_check_in = self.shift_start_time
        else:
            try:
                profile = self.user.employeeprofile
                creator_admin = profile.created_by
            except Exception:
                creator_admin = None

            if creator_admin:
                try:
                    shift_check_in = creator_admin.attendance_settings.check_in_time
                except Exception:
                    from datetime import time
                    shift_check_in = time(9, 0)
            else:
                from datetime import time
                shift_check_in = time(9, 0)

        from django.utils import timezone
        local_check_in = timezone.localtime(self.check_in)
        if local_check_in.time() > shift_check_in:
            from datetime import datetime
            dummy_check_in = datetime.combine(local_check_in.date(), local_check_in.time())
            dummy_shift_in = datetime.combine(local_check_in.date(), shift_check_in)
            return int((dummy_check_in - dummy_shift_in).total_seconds() / 60)
        return 0

    @property
    def dynamic_early_checkout_minutes(self):
        if not self.check_out:
            return 0
        if self.shift_end_time:
            shift_check_out = self.shift_end_time
        else:
            try:
                profile = self.user.employeeprofile
                creator_admin = profile.created_by
            except Exception:
                creator_admin = None

            if creator_admin:
                try:
                    shift_check_out = creator_admin.attendance_settings.check_out_time
                except Exception:
                    from datetime import time
                    shift_check_out = time(18, 0)
            else:
                from datetime import time
                shift_check_out = time(18, 0)

        from django.utils import timezone
        local_check_out = timezone.localtime(self.check_out)
        if local_check_out.time() < shift_check_out:
            from datetime import datetime
            dummy_check_out = datetime.combine(local_check_out.date(), local_check_out.time())
            dummy_shift_out = datetime.combine(local_check_out.date(), shift_check_out)
            return int((dummy_shift_out - dummy_check_out).total_seconds() / 60)
        return 0

    @property
    def dynamic_is_early_checkout(self):
        return self.dynamic_early_checkout_minutes > 0

    @property
    def calculated_salary(self):
        try:
            profile = self.user.employeeprofile
            creator_admin = profile.created_by
        except Exception:
            profile = None
            creator_admin = None

        if self.shift_start_time and self.shift_end_time:
            shift_check_in = self.shift_start_time
            shift_check_out = self.shift_end_time
            default_salary = 1000.00
            if creator_admin:
                try:
                    default_salary = float(creator_admin.attendance_settings.default_daily_salary)
                except Exception:
                    pass
        elif creator_admin:
            try:
                settings_obj = creator_admin.attendance_settings
                shift_check_in = settings_obj.check_in_time
                shift_check_out = settings_obj.check_out_time
                default_salary = float(settings_obj.default_daily_salary)
            except Exception:
                from datetime import time
                shift_check_in = time(9, 0)
                shift_check_out = time(18, 0)
                default_salary = 1000.00
        else:
            from datetime import time
            shift_check_in = time(9, 0)
            shift_check_out = time(18, 0)
            default_salary = 1000.00

        base_salary = float(profile.daily_salary) if (profile and profile.daily_salary is not None) else default_salary

        # Standard shift duration in minutes
        from datetime import datetime, timedelta
        dummy_in = datetime.combine(self.date, shift_check_in)
        dummy_out = datetime.combine(self.date, shift_check_out)
        
        # Handle cross-midnight duration calculation
        if shift_check_out < shift_check_in:
            dummy_out = dummy_out + timedelta(days=1)
            
        shift_minutes = max(1, int((dummy_out - dummy_in).total_seconds() / 60))

        late_min = self.dynamic_lateness_minutes
        early_min = self.dynamic_early_checkout_minutes

        net_minutes = shift_minutes - late_min - early_min
        if net_minutes < 0:
            net_minutes = 0

        ratio = net_minutes / shift_minutes
        if ratio > 1.0:
            ratio = 1.0

        return round(base_salary * ratio, 2)

    @property
    def overtime_hours(self):
        if not self.check_out or not self.shift_end_time or not self.shift_start_time:
            return 0.0
        from django.utils import timezone
        local_out = timezone.localtime(self.check_out)
        
        # Combine shift_end_time with correct date
        from datetime import datetime, timedelta
        shift_end_dt = datetime.combine(self.date, self.shift_end_time)
        shift_end_dt = timezone.make_aware(shift_end_dt)
        if self.shift_end_time < self.shift_start_time:
            shift_end_dt = shift_end_dt + timedelta(days=1)
            
        if local_out > shift_end_dt:
            delta = local_out - shift_end_dt
            return round(delta.total_seconds() / 3600.0, 2)
        return 0.0

    @property
    def base_daily_salary(self):
        try:
            profile = self.user.employeeprofile
            creator_admin = profile.created_by
        except Exception:
            profile = None
            creator_admin = None

        if creator_admin:
            try:
                default_salary = float(creator_admin.attendance_settings.default_daily_salary)
            except Exception:
                default_salary = 1000.00
        else:
            default_salary = 1000.00

        return float(profile.daily_salary) if (profile and profile.daily_salary is not None) else default_salary

class AttendanceLog(models.Model):
    ACTION_CHOICES = (
        ('CHECK_IN', 'Clock In'),
        ('CHECK_OUT', 'Clock Out'),
    )
    STATUS_CHOICES = (
        ('SUCCESS', 'Success'),
        ('FAILURE', 'Failure'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendance_logs')
    action = models.CharField(max_length=15, choices=ACTION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_info = models.TextField(blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    failed_attempts_count = models.IntegerField(default=0)
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    employee_name = models.CharField(max_length=150, blank=True, null=True)
    similarity_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.status}"

    @property
    def similarity_percentage(self):
        if self.similarity_score:
            return int(float(self.similarity_score) * 100)
        return 0

class AdminAttendanceSettings(models.Model):
    admin = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'ADMIN'}, related_name='attendance_settings')
    check_in_time = models.TimeField(default="09:00:00")
    check_out_time = models.TimeField(default="18:00:00")
    default_daily_salary = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    default_ot_hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=150.00)
    # Weekly working days, e.g. ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    working_days = models.JSONField(default=list)
    # Custom non-working/holiday dates, e.g. ["2026-08-15", "2026-08-25"]
    custom_holidays = models.JSONField(default=list)

    def __str__(self):
        return f"Attendance Settings for {self.admin.username}"

class OvertimeRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='overtime_records')
    date = models.DateField(default=timezone.localdate)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    calculated_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    check_in_image = models.ImageField(upload_to='attendance_captures/ot_checkin/', null=True, blank=True)
    check_out_image = models.ImageField(upload_to='attendance_captures/ot_checkout/', null=True, blank=True)
    similarity_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # Metadata snapshot fields
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    employee_name = models.CharField(max_length=150, blank=True, null=True)
    assigned_shift = models.ForeignKey('Shift', on_delete=models.SET_NULL, null=True, blank=True, related_name='overtime_records')
    shift_end_time = models.TimeField(null=True, blank=True)
    ot_status = models.CharField(max_length=20, default='APPROVED')

    class Meta:
        ordering = ['-date', '-check_in']

    def __str__(self):
        return f"OT {self.user.username} - {self.date}"

class Shift(models.Model):
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'ADMIN'}, related_name='shifts')
    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.admin.username} - {self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"

class AdminShiftConfiguration(models.Model):
    SHIFT_STRUCTURE_CHOICES = (
        ('GENERAL', 'General Shift'),
        ('MORNING_NIGHT', 'Morning and Night Shifts'),
        ('MORNING_EVENING_NIGHT', 'Morning, Evening, and Night Shifts'),
    )
    admin = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'ADMIN'}, related_name='shift_configuration')
    structure = models.CharField(max_length=30, choices=SHIFT_STRUCTURE_CHOICES, default='GENERAL')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.admin.username} - {self.get_structure_display()}"

class ShiftTimingLog(models.Model):
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shift_timing_logs')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='timing_logs')
    previous_start_time = models.TimeField()
    previous_end_time = models.TimeField()
    updated_start_time = models.TimeField()
    updated_end_time = models.TimeField()
    modified_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.admin.username} modified {self.shift.name} at {self.modified_at}"
