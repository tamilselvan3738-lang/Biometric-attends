from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.super_admin.models import OrganizationProfile, EmployeeTypeSettingAuditLog
from apps.employee_management.models import EmployeeProfile
from apps.employee_management.forms import EmployeeAddForm, EmployeeEditForm
from apps.leave_management.models import LeaveRequest
from apps.attendance.models import AttendanceRecord, Shift
from datetime import date, time, datetime

User = get_user_model()

class EmployeeTypeFeatureControlTest(TestCase):
    def setUp(self):
        # Create Super User with explicit SUPER_ADMIN role
        self.super_user = User.objects.create_superuser(
            username='superuser', 
            password='password123', 
            email='super@test.com',
            role='SUPER_ADMIN'
        )
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
            enable_employee_types=True
        )

        self.client = Client()

    def test_super_user_can_set_employee_types_enabled_yes(self):
        self.client.force_login(self.super_user)
        # Edit Admin to set enable_employee_types to Yes
        url = reverse('super_admin:edit_admin', args=[self.admin.pk])
        response = self.client.post(url, {
            'first_name': 'AdminFirst',
            'last_name': 'AdminLast',
            'email': 'admin@test.com',
            'phone_number': '1234567890',
            'is_approved': True,
            'max_employees': 10,
            'organization_name': 'Admin Org',
            'enable_overtime': 'Yes',
            'enable_employee_types': 'Yes',
            'shift_structure': 'GENERAL'
        })
        self.assertEqual(response.status_code, 302)
        
        self.org_profile.refresh_from_db()
        self.assertTrue(self.org_profile.enable_employee_types)
        
        # Verify no change log if the setting was already Yes (or same value)
        log_exists = EmployeeTypeSettingAuditLog.objects.filter(admin_name='admin').exists()
        self.assertFalse(log_exists)

    def test_super_user_can_set_employee_types_enabled_no_and_audit_log(self):
        self.client.force_login(self.super_user)
        url = reverse('super_admin:edit_admin', args=[self.admin.pk])
        response = self.client.post(url, {
            'first_name': 'AdminFirst',
            'last_name': 'AdminLast',
            'email': 'admin@test.com',
            'phone_number': '1234567890',
            'is_approved': True,
            'max_employees': 10,
            'organization_name': 'Admin Org',
            'enable_overtime': 'Yes',
            'enable_employee_types': 'No',
            'shift_structure': 'GENERAL'
        })
        self.assertEqual(response.status_code, 302)

        self.org_profile.refresh_from_db()
        self.assertFalse(self.org_profile.enable_employee_types)

        # Verify audit log was created
        log = EmployeeTypeSettingAuditLog.objects.filter(admin_name='admin').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.superuser_name, 'superuser')
        self.assertEqual(log.previous_value, 'Yes')
        self.assertEqual(log.new_value, 'No')

    def test_employee_forms_visibility_when_enabled(self):
        # When enable_employee_types is True
        self.org_profile.enable_employee_types = True
        self.org_profile.save()

        form = EmployeeAddForm(creator=self.admin)
        self.assertFalse(form.fields['employee_type'].widget.is_hidden)
        self.assertFalse(form.fields['reporting_manager'].widget.is_hidden)

    def test_employee_forms_visibility_when_disabled(self):
        # When enable_employee_types is False
        self.org_profile.enable_employee_types = False
        self.org_profile.save()

        form = EmployeeAddForm(creator=self.admin)
        self.assertTrue(form.fields['employee_type'].widget.is_hidden)
        self.assertTrue(form.fields['reporting_manager'].widget.is_hidden)
        
        # Verify clean defaults values safely
        self.assertEqual(form.fields['employee_type'].initial, 'EMPLOYEE')
        self.assertIsNone(form.fields['reporting_manager'].initial)

    def test_leave_approval_routing_when_employee_types_disabled(self):
        # Set enable_employee_types to False
        self.org_profile.enable_employee_types = False
        self.org_profile.save()

        # Create shift
        shift = Shift.objects.create(admin=self.admin, name="General", start_time=time(9, 0), end_time=time(17, 0))

        # Create regular employee
        emp = User.objects.create_user(username='emp', password='password123', email='emp@test.com', role='EMPLOYEE')
        emp_profile = EmployeeProfile.objects.create(
            user=emp,
            employee_id="EMP_101",
            employee_type="EMPLOYEE",
            designation="Staff",
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=shift
        )

        # Apply leave request
        self.client.force_login(emp)
        url = reverse('leave_management:apply_leave')
        response = self.client.post(url, {
            'leave_type': 'CASUAL',
            'start_date': '2026-08-01',
            'end_date': '2026-08-05',
            'reason': 'Vacation'
        })
        self.assertEqual(response.status_code, 302)

        # Verify the leave was created
        leave = LeaveRequest.objects.filter(user=emp).first()
        self.assertIsNotNone(leave)
        
        # Verify the leave requests view for Admin lists this leave
        self.client.force_login(self.admin)
        url_requests = reverse('leave_management:leave_requests')
        response_requests = self.client.get(url_requests)
        self.assertEqual(response_requests.status_code, 200)
        self.assertIn(leave, response_requests.context['pending_leaves'])

    def test_access_controls_restricted_when_employee_types_disabled(self):
        # Set enable_employee_types to False
        self.org_profile.enable_employee_types = False
        self.org_profile.save()

        # Create shift
        shift = Shift.objects.create(admin=self.admin, name="General", start_time=time(9, 0), end_time=time(17, 0))

        # Create a user with manager role
        manager = User.objects.create_user(username='manager', password='password123', email='manager@test.com', role='EMPLOYEE')
        emp_profile = EmployeeProfile.objects.create(
            user=manager,
            employee_id="EMP_102",
            employee_type="MANAGER",
            designation="Manager",
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=shift
        )

        # Since enable_employee_types is False, the manager's properties (is_manager) will return False
        self.assertFalse(manager.is_manager)

        # Try to access admin/manager-specific leave requests dashboard
        self.client.force_login(manager)
        url = reverse('leave_management:leave_requests')
        response = self.client.get(url)
        # Should redirect (302) to dispatcher because access is restricted to Admin
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboards:dispatcher'), response.url)
