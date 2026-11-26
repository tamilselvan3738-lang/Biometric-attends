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

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_ot_enabled:
            self.fields['default_ot_hourly_rate'].required = False

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
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 2}),
        required=True,
        label="Reason for Change"
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
        # All calculations and status updates are handled automatically by the model's save method
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
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 2}),
        required=True,
        label="Reason for Change"
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
