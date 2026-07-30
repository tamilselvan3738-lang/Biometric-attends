from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.attendance.models import AttendanceRecord, Shift, AdminShiftConfiguration, ShiftTimingLog
from apps.employee_management.models import EmployeeProfile
from apps.super_admin.forms import AdminAddForm, AdminEditForm
from apps.employee_management.forms import EmployeeAddForm, EmployeeEditForm
from datetime import timedelta, time, datetime

User = get_user_model()

class AttendanceTestCase(TestCase):
    def setUp(self):
        # Create Super Admin
        self.super_admin = User.objects.create_superuser(
            username='super_admin',
            email='super@example.com',
            password='password123'
        )
        
        # Create Admin
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@example.com',
            password='password123',
            role='ADMIN'
        )
        
        # Create default shift configuration
        self.config = AdminShiftConfiguration.objects.create(admin=self.admin, structure='GENERAL')
        self.shift = Shift.objects.create(admin=self.admin, name='General Shift', start_time=time(9, 0), end_time=time(18, 0))
        
        # Create Employee
        self.employee_user = User.objects.create_user(
            username='emp_test',
            email='test@example.com',
            password='password123',
            role='EMPLOYEE'
        )
        self.profile = EmployeeProfile.objects.create(
            user=self.employee_user,
            employee_id='admin_test_emp1',
            designation='Software Engineer',
            date_of_joining=timezone.localdate(),
            created_by=self.admin,
            shift=self.shift
        )

    def test_create_attendance_record(self):
        now = timezone.now()
        record = AttendanceRecord.objects.create(
            user=self.employee_user,
            check_in=now,
            status='PRESENT',
            shift=self.shift,
            shift_name=self.shift.name,
            shift_start_time=self.shift.start_time,
            shift_end_time=self.shift.end_time
        )
        self.assertEqual(record.status, 'PRESENT')
        self.assertIsNone(record.check_out)
        self.assertEqual(record.shift_name, 'General Shift')

    def test_checkout_and_hours_calculation(self):
        now = timezone.now()
        check_in_time = now - timedelta(hours=8)
        record = AttendanceRecord.objects.create(
            user=self.employee_user,
            check_in=check_in_time,
            status='PRESENT',
            shift=self.shift,
            shift_name=self.shift.name,
            shift_start_time=self.shift.start_time,
            shift_end_time=self.shift.end_time
        )
        
        # Simulate checkout
        record.check_out = now
        delta = record.check_out - record.check_in
        record.total_hours = round(delta.total_seconds() / 3600.0, 2)
        record.save()
        
        self.assertEqual(float(record.total_hours), 8.0)

    def test_shift_auto_generation_on_admin_add(self):
        # Test shift structure creation and auto shift slots generation
        # We can simulate AdminAddForm save
        form_data = {
            'username': 'new_admin',
            'password': 'password123',
            'email': 'new_admin@example.com',
            'first_name': 'New',
            'last_name': 'Admin',
            'phone_number': '1234567890',
            'max_employees': 5,
            'organization_name': 'New Org',
            'gstin': '',
            'shift_structure': 'MORNING_NIGHT'
        }
        form = AdminAddForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        admin = form.save()
        
        # Verify configuration
        config = AdminShiftConfiguration.objects.get(admin=admin)
        self.assertEqual(config.structure, 'MORNING_NIGHT')
        
        # Verify shifts
        shifts = Shift.objects.filter(admin=admin)
        self.assertEqual(shifts.count(), 2)
        shift_names = [s.name for s in shifts]
        self.assertIn('Morning Shift', shift_names)
        self.assertIn('Night Shift', shift_names)

    def test_shift_timing_modification_logging(self):
        # Admin modifies shift timings
        prev_start = self.shift.start_time
        prev_end = self.shift.end_time
        
        new_start = time(10, 0)
        new_end = time(19, 0)
        
        # Modify
        self.shift.start_time = new_start
        self.shift.end_time = new_end
        self.shift.save()
        
        # Create log entry (as would views.py)
        log = ShiftTimingLog.objects.create(
            admin=self.admin,
            shift=self.shift,
            previous_start_time=prev_start,
            previous_end_time=prev_end,
            updated_start_time=new_start,
            updated_end_time=new_end
        )
        
        self.assertEqual(log.shift, self.shift)
        self.assertEqual(log.previous_start_time, prev_start)
        self.assertEqual(log.updated_start_time, new_start)

    def test_employee_form_shift_scoping(self):
        # Test EmployeeAddForm scopes shifts to the admin
        form = EmployeeAddForm(creator=self.admin)
        shift_field_queryset = form.fields['shift'].queryset
        self.assertIn(self.shift, shift_field_queryset)

    def test_lateness_and_overtime_calculation(self):
        # Set shift starting at 9:00 AM, ending at 6:00 PM
        # Check in at 9:30 AM
        today = timezone.localdate()
        check_in = timezone.make_aware(datetime.combine(today, time(9, 30)))
        
        record = AttendanceRecord.objects.create(
            user=self.employee_user,
            date=today,
            check_in=check_in,
            shift=self.shift,
            shift_name=self.shift.name,
            shift_start_time=self.shift.start_time,
            shift_end_time=self.shift.end_time
        )
        self.assertEqual(record.dynamic_lateness_minutes, 30)
        
        # Check out at 7:00 PM (1 hour overtime)
        check_out = timezone.make_aware(datetime.combine(today, time(19, 0)))
        record.check_out = check_out
        record.save()
        self.assertEqual(record.overtime_hours, 1.0)

    def test_custom_shift_settings_post(self):
        self.client.login(username='admin_test', password='password123')
        post_data = {
            'check_in_time': '09:00:00',
            'check_out_time': '18:00:00',
            'default_daily_salary': '1200.00',
            'default_ot_hourly_rate': '150.00',
            'working_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            f'shift_{self.shift.id}_start': '08:00',
            f'shift_{self.shift.id}_end': '17:00',
        }
        response = self.client.post('/attendance/settings/', data=post_data)
        self.assertEqual(response.status_code, 302)
        
        self.shift.refresh_from_db()
        self.assertEqual(self.shift.start_time, time(8, 0))
        self.assertEqual(self.shift.end_time, time(17, 0))

    def test_check_in_window_restriction(self):
        from apps.attendance.views import get_active_shift_date_for_employee
        from unittest.mock import patch
        
        today = timezone.localdate()
        # Scenario 1: Current local time is 45 minutes before shift start -> Should fail
        # Shift starts at 09:00 AM. 45 minutes before is 08:15 AM
        target_dt = timezone.make_aware(datetime.combine(today, time(8, 15)))
        with patch('django.utils.timezone.now', return_value=target_dt):
            matching_date, msg = get_active_shift_date_for_employee(self.employee_user)
            self.assertIsNone(matching_date)
            self.assertIn("Check-in is not yet available", msg)
            
        # Scenario 2: Current local time is 20 minutes before shift start -> Should succeed
        # Shift starts at 09:00 AM. 20 minutes before is 08:40 AM
        target_dt = timezone.make_aware(datetime.combine(today, time(8, 40)))
        with patch('django.utils.timezone.now', return_value=target_dt):
            matching_date, msg = get_active_shift_date_for_employee(self.employee_user)
            self.assertEqual(matching_date, today)
            self.assertIsNone(msg)

    def test_ot_eligibility_checks(self):
        from apps.attendance.views import check_ot_eligibility
        from unittest.mock import patch
        
        today = timezone.localdate()
        # Scenario 1: Regular shift is still active -> Should fail
        # Shift is 09:00 AM to 06:00 PM. Local time is 03:00 PM
        target_dt = timezone.make_aware(datetime.combine(today, time(15, 0)))
        with patch('django.utils.timezone.now', return_value=target_dt):
            eligible, msg = check_ot_eligibility(self.employee_user)
            self.assertFalse(eligible)
            self.assertIn("regular shift", msg)
            
        # Scenario 2: Shift ended, but no regular attendance -> Should fail
        # Shift ended at 06:00 PM. Local time is 07:00 PM
        target_dt = timezone.make_aware(datetime.combine(today, time(19, 0)))
        with patch('django.utils.timezone.now', return_value=target_dt):
            eligible, msg = check_ot_eligibility(self.employee_user)
            self.assertFalse(eligible)
            self.assertIn("You must check in and check out", msg)

        # Scenario 3: Shift ended, checked in but not checked out -> Should fail
        AttendanceRecord.objects.create(
            user=self.employee_user,
            date=today,
            check_in=timezone.make_aware(datetime.combine(today, time(9, 0)))
        )
        target_dt = timezone.make_aware(datetime.combine(today, time(19, 0)))
        with patch('django.utils.timezone.now', return_value=target_dt):
            eligible, msg = check_ot_eligibility(self.employee_user)
            self.assertFalse(eligible)
            self.assertIn("check out of your regular shift", msg)

        # Scenario 4: Shift ended, fully checked in and out -> Should succeed!
        record = AttendanceRecord.objects.get(user=self.employee_user, date=today)
        record.check_out = timezone.make_aware(datetime.combine(today, time(18, 0)))
        record.save()
        
        target_dt = timezone.make_aware(datetime.combine(today, time(19, 0)))
        with patch('django.utils.timezone.now', return_value=target_dt):
            eligible, result = check_ot_eligibility(self.employee_user)
            self.assertTrue(eligible)
            self.assertEqual(result, today)

    def test_multi_frame_face_verification(self):
        from apps.attendance.views import perform_face_verification
        from apps.biometric.face_engine import FaceEngine
        from apps.biometric.models import FaceEnrollment
        from unittest.mock import patch
        import json
        
        # Register a face enrollment for the employee
        FaceEnrollment.objects.create(
            user=self.employee_user,
            face_data=json.dumps({'templates': [[1, 2, 3]]})
        )
        
        # Scenario: perform_face_verification helper works correctly with multiple frames
        # We mock extract_face and compute_similarity to control similarity scores.
        with patch('apps.biometric.face_engine.FaceEngine.decode_base64_image') as mock_decode, \
             patch('apps.biometric.face_engine.FaceEngine.extract_face') as mock_extract, \
             patch('apps.biometric.face_engine.FaceEngine.validate_face_quality') as mock_quality, \
             patch('apps.biometric.face_engine.FaceEngine.compute_similarity') as mock_similarity, \
             patch('apps.biometric.face_engine.FaceEngine.get_matching_details') as mock_details:
             
            # Setup mocks
            mock_decode.return_value = object()
            mock_extract.return_value = (object(), {'x': 10, 'y': 10, 'w': 100, 'h': 100})
            mock_quality.return_value = (True, "OK", 95.0, {})
            mock_details.return_value = {'composite_similarity': 0.76}
            mock_similarity.return_value = 0.76
            
            # 1. Verification succeeds if best matching frame is >= 0.75
            from django.test import RequestFactory
            factory = RequestFactory()
            req = factory.post('/fake-url/')
            req.user = self.employee_user
            req.META['HTTP_USER_AGENT'] = 'FakeUA'

            images_list = ["img1", "img2", "img3", "img4", "img5"]
            result = perform_face_verification(req, 'CHECK_IN', images_list)
            self.assertTrue(result['success'])
            self.assertEqual(result['similarity_score'], 0.76)
            
            # 2. Verification fails if best matching frame is < 0.75
            mock_similarity.return_value = 0.72
            mock_details.return_value = {'composite_similarity': 0.72}
            result = perform_face_verification(req, 'CHECK_IN', images_list)
            self.assertFalse(result['success'])
            self.assertIn("Face verification failed", result['message'])

    def test_ot_check_out_view(self):
        from apps.attendance.models import OvertimeRecord
        self.client.login(username='emp_test', password='password123')
        
        # Case 1: No active OT check-in
        response = self.client.get('/attendance/ot-check-out/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_active_ot_checkin'])
        self.assertFalse(response.context['already_checked_out'])
        
        # Case 2: Active OT check-in exists
        today = timezone.localdate()
        record = OvertimeRecord.objects.create(
            user=self.employee_user,
            date=today,
            check_in=timezone.now(),
            hourly_rate=150.0
        )
        response = self.client.get('/attendance/ot-check-out/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['has_active_ot_checkin'])
        self.assertFalse(response.context['already_checked_out'])
        
        # Case 3: Checked out
        record.check_out = timezone.now()
        record.save()
        response = self.client.get('/attendance/ot-check-out/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_active_ot_checkin'])
        self.assertTrue(response.context['already_checked_out'])

    def test_employee_custom_timings_lateness_and_window(self):
        from apps.attendance.views import get_active_shift_date_for_employee
        from unittest.mock import patch
        
        today = timezone.localdate()
        # Set custom timing for the employee
        # Shift slot is 09:00 AM to 06:00 PM. We customize it to 10:00 AM to 07:00 PM.
        self.profile.custom_check_in_time = time(10, 0)
        self.profile.custom_check_out_time = time(19, 0)
        self.profile.save()
        
        # 1. Active window: starts exactly 30 minutes before 10:00 AM (i.e. 09:30 AM).
        # Let's test at 09:20 AM -> Should be blocked
        target_dt = timezone.make_aware(datetime.combine(today, time(9, 20)))
        with patch('django.utils.timezone.now', return_value=target_dt):
            matching_date, msg = get_active_shift_date_for_employee(self.employee_user)
            self.assertIsNone(matching_date)
            self.assertIn("Check-in is not yet available", msg)
            
        # 2. Test at 09:40 AM -> Should succeed
        target_dt = timezone.make_aware(datetime.combine(today, time(9, 40)))
        with patch('django.utils.timezone.now', return_value=target_dt):
            matching_date, msg = get_active_shift_date_for_employee(self.employee_user)
            self.assertEqual(matching_date, today)
            self.assertIsNone(msg)

    def test_employee_timing_audit_logging(self):
        from apps.employee_management.models import EmployeeTimingAuditLog
        from apps.departments.models import Department
        
        dept = Department.objects.create(name='Engineering', code='ENG', manager=self.admin)
        self.profile.department = dept
        self.profile.save()
        
        self.client.login(username='admin_test', password='password123')
        
        # Create form POST request to modify timings
        data = {
            'first_name': 'Test',
            'last_name': 'Employee',
            'email': 'test@example.com',
            'phone_number': '12345678',
            'gender': 'MALE',
            'department': dept.id,
            'designation': self.profile.designation,
            'date_of_joining': self.profile.date_of_joining.strftime('%Y-%m-%d'),
            'status': 'ACTIVE',
            'shift': self.shift.id,
            'custom_check_in_time': '10:00:00',
            'custom_check_out_time': '18:00:00'
        }
        response = self.client.post(f'/employees/edit/{self.profile.id}/', data)
        self.assertEqual(response.status_code, 302) # Redirects on success
        
        # Verify audit log was created
        audit_log = EmployeeTimingAuditLog.objects.filter(employee_profile=self.profile).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.employee_id, self.profile.display_employee_id)
        self.assertEqual(audit_log.updated_check_in_time, time(10, 0))
        self.assertEqual(audit_log.updated_check_out_time, time(18, 0))
        self.assertEqual(audit_log.modified_by, self.admin)

    def test_employee_shift_reassignment_and_audit(self):
        from apps.employee_management.models import EmployeeShiftAuditLog
        from apps.notifications.models import Notification
        from apps.attendance.models import Shift
        from apps.departments.models import Department
        
        # 1. Create a second shift slot and a department
        other_shift = Shift.objects.create(
            name="Night Shift",
            start_time=time(22, 0),
            end_time=time(6, 0),
            admin=self.admin
        )
        dept = Department.objects.create(name='Engineering', code='ENG', manager=self.admin)
        self.profile.department = dept
        self.profile.save()
        
        # 2. Login as the admin
        self.client.login(username='admin_test', password='password123')
        
        # 3. Post to change shift slot
        data = {
            'first_name': 'Test',
            'last_name': 'Employee',
            'email': 'test@example.com',
            'phone_number': '12345678',
            'gender': 'MALE',
            'department': dept.id,
            'designation': self.profile.designation,
            'date_of_joining': self.profile.date_of_joining.strftime('%Y-%m-%d'),
            'status': 'ACTIVE',
            'shift': other_shift.id,
        }
        response = self.client.post(f'/employees/edit/{self.profile.id}/', data)
        self.assertEqual(response.status_code, 302)
        
        # 4. Verify audit log was created
        audit_log = EmployeeShiftAuditLog.objects.filter(employee_profile=self.profile).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.employee_id, self.profile.display_employee_id)
        self.assertEqual(audit_log.previous_shift, self.shift)
        self.assertEqual(audit_log.new_shift, other_shift)
        self.assertEqual(audit_log.modified_by, self.admin)
        
        # 5. Verify notification was created for employee
        notif = Notification.objects.filter(recipient=self.employee_user).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, "Shift Assignment Updated")
        self.assertIn("Night Shift", notif.message)
