from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
from apps.super_admin.models import OrganizationProfile
from apps.employee_management.models import EmployeeProfile, EmployeeOTSettingAuditLog
from apps.employee_management.forms import EmployeeAddForm, EmployeeEditForm
from apps.departments.models import Department
from apps.attendance.models import Shift
from datetime import date, time

User = get_user_model()

class EmployeeOTConfigurationTest(TestCase):
    def setUp(self):
        # Create Admin
        self.admin = User.objects.create_user(
            username='admin', 
            password='password123', 
            email='admin@test.com', 
            role='ADMIN'
        )
        self.org_profile = OrganizationProfile.objects.create(
            admin=self.admin, 
            name="Admin Org", 
            enable_overtime=True,
            enable_employee_types=True
        )
        
        # Create Department
        self.dept = Department.objects.create(name="Engineering", code="ENG")
        
        # Create Shift
        self.shift = Shift.objects.create(
            admin=self.admin,
            name="General Shift",
            start_time=time(9, 0),
            end_time=time(18, 0)
        )
        
        self.client = Client()

    def test_ot_enabled_employee_types_enabled_hr_team_needs_ot_checkin_validation(self):
        self.org_profile.enable_overtime = True
        self.org_profile.enable_employee_types = True
        self.org_profile.save()

        # Try registering an HR Team member without need_ot_check_in value
        form = EmployeeAddForm(creator=self.admin, data={
            'username': 'hr1',
            'password': 'password123',
            'email': 'hr1@test.com',
            'first_name': 'HR',
            'last_name': 'Team',
            'gender': 'MALE',
            'employee_id': 'HR001',
            'employee_type': 'HR_TEAM',
            'department': self.dept.pk,
            'designation': 'HR Executive',
            'date_of_joining': '2026-08-01',
            'status': 'ACTIVE',
            'shift': self.shift.pk,
            'need_ot_check_in': '' # Empty - should trigger validation error
        })
        self.assertFalse(form.is_valid())
        self.assertIn('need_ot_check_in', form.errors)

    @patch('apps.biometric.face_engine.FaceEngine.register_face')
    def test_ot_enabled_employee_types_enabled_hr_team_ot_allowed(self, mock_register):
        mock_register.return_value = (True, [0.1]*512, b'thumbnail', "Success", 95.0, {}, {})
        
        self.org_profile.enable_overtime = True
        self.org_profile.enable_employee_types = True
        self.org_profile.save()

        # Register HR Team with Need OT = Yes
        self.client.force_login(self.admin)
        url = reverse('employee_management:add_employee')
        response = self.client.post(url, {
            'username': 'hr_yes',
            'password': 'password123',
            'email': 'hryes@test.com',
            'first_name': 'HR',
            'last_name': 'Yes',
            'gender': 'MALE',
            'employee_id': 'HRY001',
            'employee_type': 'HR_TEAM',
            'department': self.dept.pk,
            'designation': 'HR Executive',
            'date_of_joining': '2026-08-01',
            'status': 'ACTIVE',
            'shift': self.shift.pk,
            'need_ot_check_in': 'Yes',
            'face_images': '["dummy_base64_image"]'
        })
        if response.status_code != 302:
            print("ADD FORM ERRORS:", response.context['form'].errors)
        self.assertEqual(response.status_code, 302)

        # Retrieve user and verify is_ot_enabled
        user_yes = User.objects.get(username='admin_hr_yes')
        self.assertTrue(user_yes.is_ot_enabled)

        # Verify audit log was created
        log = EmployeeOTSettingAuditLog.objects.filter(username='admin_hr_yes').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.employee_type, 'HR_TEAM')
        self.assertEqual(log.ot_permission_status, 'Yes')
        self.assertEqual(log.created_by, 'admin')

    @patch('apps.biometric.face_engine.FaceEngine.register_face')
    def test_ot_enabled_employee_types_enabled_hr_team_ot_disabled(self, mock_register):
        mock_register.return_value = (True, [0.1]*512, b'thumbnail', "Success", 95.0, {}, {})
        
        self.org_profile.enable_overtime = True
        self.org_profile.enable_employee_types = True
        self.org_profile.save()

        # Register HR Team with Need OT = No
        self.client.force_login(self.admin)
        url = reverse('employee_management:add_employee')
        response = self.client.post(url, {
            'username': 'hr_no',
            'password': 'password123',
            'email': 'hrno@test.com',
            'first_name': 'HR',
            'last_name': 'No',
            'gender': 'MALE',
            'employee_id': 'HRN001',
            'employee_type': 'HR_TEAM',
            'department': self.dept.pk,
            'designation': 'HR Executive',
            'date_of_joining': '2026-08-01',
            'status': 'ACTIVE',
            'shift': self.shift.pk,
            'need_ot_check_in': 'No',
            'face_images': '["dummy_base64_image"]'
        })
        self.assertEqual(response.status_code, 302)

        # Retrieve user and verify is_ot_enabled
        user_no = User.objects.get(username='admin_hr_no')
        self.assertFalse(user_no.is_ot_enabled)

        # Verify audit log was created
        log = EmployeeOTSettingAuditLog.objects.filter(username='admin_hr_no').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.ot_permission_status, 'No')

    @patch('apps.biometric.face_engine.FaceEngine.register_face')
    def test_ot_enabled_employee_types_enabled_standard_employee(self, mock_register):
        mock_register.return_value = (True, [0.1]*512, b'thumbnail', "Success", 95.0, {}, {})
        
        self.org_profile.enable_overtime = True
        self.org_profile.enable_employee_types = True
        self.org_profile.save()

        # Manager user for reporting manager assignment
        manager = User.objects.create_user(username='admin_manager', password='password123', role='EMPLOYEE')
        EmployeeProfile.objects.create(
            user=manager,
            employee_id='admin_MGR001',
            employee_type='MANAGER',
            designation='Mgr',
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=self.shift
        )

        # Register regular Employee (should not display/require need_ot_check_in and be enabled by default)
        self.client.force_login(self.admin)
        url = reverse('employee_management:add_employee')
        response = self.client.post(url, {
            'username': 'emp1',
            'password': 'password123',
            'email': 'emp1@test.com',
            'first_name': 'Emp',
            'last_name': 'One',
            'gender': 'MALE',
            'employee_id': 'EMP001',
            'employee_type': 'EMPLOYEE',
            'reporting_manager': manager.pk,
            'department': self.dept.pk,
            'designation': 'Staff',
            'date_of_joining': '2026-08-01',
            'status': 'ACTIVE',
            'shift': self.shift.pk,
            'face_images': '["dummy_base64_image"]'
        })
        self.assertEqual(response.status_code, 302)

        # Retrieve user and verify is_ot_enabled is True
        user_emp = User.objects.get(username='admin_emp1')
        self.assertTrue(user_emp.is_ot_enabled)

        # Verify audit log recorded 'Yes'
        log = EmployeeOTSettingAuditLog.objects.filter(username='admin_emp1').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.ot_permission_status, 'Yes')

    def test_ot_disabled_hides_ot_for_all(self):
        # OT disabled at organization level
        self.org_profile.enable_overtime = False
        self.org_profile.enable_employee_types = True
        self.org_profile.save()

        # Regular employee
        emp = User.objects.create_user(username='admin_emp2', password='password123', role='EMPLOYEE')
        profile = EmployeeProfile.objects.create(
            user=emp,
            employee_id='admin_EMP002',
            employee_type='EMPLOYEE',
            designation='Staff',
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=self.shift,
            need_ot_check_in=True
        )

        # Even with need_ot_check_in=True, since enable_overtime is False, is_ot_enabled must be False
        self.assertFalse(emp.is_ot_enabled)

        # Check forms have need_ot_check_in hidden
        form = EmployeeAddForm(creator=self.admin)
        self.assertTrue(form.fields['need_ot_check_in'].widget.is_hidden)

    def test_ot_settings_change_audit_logs_modified_by(self):
        # Start with OT = True, Employee Types = True
        self.org_profile.enable_overtime = True
        self.org_profile.enable_employee_types = True
        self.org_profile.save()

        # Create Manager with OT Yes
        mgr = User.objects.create_user(username='admin_mgr2', password='password123', role='EMPLOYEE')
        profile = EmployeeProfile.objects.create(
            user=mgr,
            employee_id='admin_MGR002',
            employee_type='MANAGER',
            designation='Manager',
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=self.shift,
            need_ot_check_in=True
        )

        # Update manager's OT setting to No
        self.client.force_login(self.admin)
        url = reverse('employee_management:edit_employee', args=[profile.pk])
        response = self.client.post(url, {
            'email': 'mgr2@test.com',
            'first_name': 'Manager',
            'last_name': 'Two',
            'phone_number': '1234567890',
            'gender': 'MALE',
            'employee_type': 'MANAGER',
            'department': self.dept.pk,
            'designation': 'Manager',
            'date_of_joining': '2026-08-01',
            'status': 'ACTIVE',
            'shift': self.shift.pk,
            'need_ot_check_in': 'No' # Change to No
        })
        self.assertEqual(response.status_code, 302)

        # Refresh
        profile.refresh_from_db()
        self.assertFalse(profile.need_ot_check_in)
        self.assertFalse(mgr.is_ot_enabled)

        # Verify Audit Log
        log = EmployeeOTSettingAuditLog.objects.filter(username='admin_mgr2', modified_by='admin').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.ot_permission_status, 'No')
