from django import forms
from .models import AdminAttendanceSettings, AttendanceRecord, OvertimeRecord

class AdminAttendanceSettingsForm(forms.ModelForm):
    WEEKDAYS = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]
    working_days = forms.MultipleChoiceField(
        choices=WEEKDAYS,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input bg-dark border-secondary'}),
        required=True
    )
    custom_holidays_json = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = AdminAttendanceSettings
        fields = ['check_in_time', 'check_out_time', 'default_daily_salary', 'default_ot_hourly_rate']
        widgets = {
            'check_in_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control bg-dark text-light border-secondary'}),
            'check_out_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control bg-dark text-light border-secondary'}),
            'default_daily_salary': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'default_ot_hourly_rate': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
        }

class AttendanceRecordEditForm(forms.ModelForm):
    check_in = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control bg-dark text-light border-secondary'}),
        required=True
    )
    check_out = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control bg-dark text-light border-secondary'}),
        required=False
    )
    status = forms.ChoiceField(
        choices=AttendanceRecord.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )

    class Meta:
        model = AttendanceRecord
        fields = ['check_in', 'check_out', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            if self.instance.check_in:
                # Format to local time string for input
                from django.utils import timezone
                local_check_in = timezone.localtime(self.instance.check_in)
                self.initial['check_in'] = local_check_in.strftime('%Y-%m-%dT%H:%M')
            if self.instance.check_out:
                from django.utils import timezone
                local_check_out = timezone.localtime(self.instance.check_out)
                self.initial['check_out'] = local_check_out.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')

        if check_in and check_out and check_in > check_out:
            raise forms.ValidationError("Check-out time cannot be before check-in time.")
        return cleaned_data

    def save(self, commit=True):
        record = super().save(commit=False)
        if record.check_in and record.check_out:
            delta = record.check_out - record.check_in
            record.total_hours = round(delta.total_seconds() / 3600.0, 2)
        else:
            record.total_hours = None
            
        # Recalculate lateness and early checkout based on Admin settings
        from django.utils import timezone
        from datetime import time, datetime
        
        try:
            profile = record.user.employeeprofile
            creator_admin = profile.created_by
        except Exception:
            creator_admin = None

        if creator_admin:
            try:
                settings_obj = creator_admin.attendance_settings
                shift_check_in = settings_obj.check_in_time
                shift_check_out = settings_obj.check_out_time
            except Exception:
                shift_check_in = time(9, 0)
                shift_check_out = time(18, 0)
        else:
            shift_check_in = time(9, 0)
            shift_check_out = time(18, 0)

        # 1. Check Lateness
        if record.check_in:
            local_check_in = timezone.localtime(record.check_in)
            dummy_in = datetime.combine(local_check_in.date(), shift_check_in)
            if local_check_in.time() > shift_check_in:
                dummy_check_in = datetime.combine(local_check_in.date(), local_check_in.time())
                delta_late = dummy_check_in - dummy_in
                record.lateness_minutes = int(delta_late.total_seconds() / 60)
                record.status = 'LATE'
            else:
                record.lateness_minutes = 0
                record.status = 'PRESENT'

        # 2. Check Early Checkout
        if record.check_out:
            local_check_out = timezone.localtime(record.check_out)
            dummy_out = datetime.combine(local_check_out.date(), shift_check_out)
            if local_check_out.time() < shift_check_out:
                dummy_check_out = datetime.combine(local_check_out.date(), local_check_out.time())
                delta_early = dummy_out - dummy_check_out
                record.early_checkout_minutes = int(delta_early.total_seconds() / 60)
                record.is_early_checkout = True
            else:
                record.early_checkout_minutes = 0
                record.is_early_checkout = False
        else:
            record.early_checkout_minutes = 0
            record.is_early_checkout = False
            
        if commit:
            record.save()
        return record

class OvertimeRecordEditForm(forms.ModelForm):
    check_in = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control bg-dark text-light border-secondary'}),
        required=True
    )
    check_out = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control bg-dark text-light border-secondary'}),
        required=False
    )

    class Meta:
        model = OvertimeRecord
        fields = ['check_in', 'check_out']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            if self.instance.check_in:
                from django.utils import timezone
                local_check_in = timezone.localtime(self.instance.check_in)
                self.initial['check_in'] = local_check_in.strftime('%Y-%m-%dT%H:%M')
            if self.instance.check_out:
                from django.utils import timezone
                local_check_out = timezone.localtime(self.instance.check_out)
                self.initial['check_out'] = local_check_out.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')

        if check_in and check_out and check_in > check_out:
            raise forms.ValidationError("Check-out time cannot be before check-in time.")
        return cleaned_data

    def save(self, commit=True):
        record = super().save(commit=False)
        if record.check_in and record.check_out:
            delta = record.check_out - record.check_in
            record.total_hours = round(delta.total_seconds() / 3600.0, 2)
            record.calculated_amount = round(float(record.total_hours) * float(record.hourly_rate), 2)
        else:
            record.total_hours = None
            record.calculated_amount = 0.00
            
        if commit:
            record.save()
        return record
