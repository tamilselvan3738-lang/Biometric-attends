from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.attendance.models import AttendanceRecord, Shift
from apps.employee_management.models import EmployeeProfile
from apps.attendance.forms import AttendanceRecordEditForm
from datetime import date, time, datetime, timedelta

User = get_user_model()

class AttendanceStatusCalculationTest(TestCase):
    def setUp(self):
        # 1. Create Admin
        self.admin = User.objects.create_user(username='admin', password='password123', email='admin@test.com', role='ADMIN')
        
        # 2. Create Shift (9 AM to 5 PM)
        self.shift = Shift.objects.create(
            admin=self.admin,
            name="General Shift",
            start_time=time(9, 0),
            end_time=time(17, 0)
        )
        
        # 3. Create Employee
        self.emp_user = User.objects.create_user(username='emp1', password='password123', email='emp1@test.com', role='EMPLOYEE')
        self.emp_profile = EmployeeProfile.objects.create(
            user=self.emp_user,
            employee_id="EMP_001",
            employee_type="EMPLOYEE",
            designation="Regular Employee",
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=self.shift
        )

    def test_on_time_check_in_status(self):
        # Check in at 8:55 AM (on time)
        matching_date = date.today()
        check_in_time = timezone.make_aware(datetime.combine(matching_date, time(8, 55)))
        
        record = AttendanceRecord.objects.create(
            user=self.emp_user,
            date=matching_date,
            check_in=check_in_time,
            shift=self.shift,
            shift_start_time=self.shift.start_time,
            shift_end_time=self.shift.end_time
        )
        
        self.assertEqual(record.status, 'PRESENT')
        self.assertEqual(record.lateness_minutes, 0)

    def test_late_check_in_status(self):
        # Check in at 9:15 AM (15 mins late)
        matching_date = date.today()
        check_in_time = timezone.make_aware(datetime.combine(matching_date, time(9, 15)))
        
        record = AttendanceRecord.objects.create(
            user=self.emp_user,
            date=matching_date,
            check_in=check_in_time,
            shift=self.shift,
            shift_start_time=self.shift.start_time,
            shift_end_time=self.shift.end_time
        )
        
        self.assertEqual(record.status, 'LATE')
        self.assertEqual(record.lateness_minutes, 15)

    def test_half_day_check_out_status(self):
        # Check in at 9:00 AM, check out at 11:30 AM (2.5 hours worked out of 8 hours shift)
        matching_date = date.today()
        check_in_time = timezone.make_aware(datetime.combine(matching_date, time(9, 0)))
        check_out_time = timezone.make_aware(datetime.combine(matching_date, time(11, 30)))
        
        record = AttendanceRecord.objects.create(
            user=self.emp_user,
            date=matching_date,
            check_in=check_in_time,
            check_out=check_out_time,
            shift=self.shift,
            shift_start_time=self.shift.start_time,
            shift_end_time=self.shift.end_time
        )
        
        self.assertEqual(record.status, 'HALF_DAY')
        self.assertEqual(record.total_hours, 2.5)
        self.assertEqual(record.is_early_checkout, True)

    def test_form_edit_updates_status_automatically(self):
        # Create an initial on-time record
        matching_date = date.today()
        check_in_time = timezone.make_aware(datetime.combine(matching_date, time(9, 0)))
        
        record = AttendanceRecord.objects.create(
            user=self.emp_user,
            date=matching_date,
            check_in=check_in_time,
            shift=self.shift,
            shift_start_time=self.shift.start_time,
            shift_end_time=self.shift.end_time
        )
        self.assertEqual(record.status, 'PRESENT')
        
        # Now edit via the form to check in late (9:30 AM) and check out early (11:00 AM)
        new_check_in = timezone.make_aware(datetime.combine(matching_date, time(9, 30)))
        new_check_out = timezone.make_aware(datetime.combine(matching_date, time(11, 0)))
        
        form_data = {
            'check_in': new_check_in,
            'check_out': new_check_out,
            'status': 'PRESENT',  # Form suggests PRESENT, but it should automatically recalculate to HALF_DAY!
            'reason': 'Adjusting times'
        }
        
        form = AttendanceRecordEditForm(form_data, instance=record)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        
        record.refresh_from_db()
        # Verify status automatically recalculated to HALF_DAY due to short duration
        self.assertEqual(record.status, 'HALF_DAY')
        self.assertEqual(record.total_hours, 1.5)
        self.assertEqual(record.lateness_minutes, 30)
