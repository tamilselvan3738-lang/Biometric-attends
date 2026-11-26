from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.employee_management.models import EmployeeProfile, EmployeeTimingAuditLog
from apps.leave_management.models import LeaveRequest, LeaveApprovalAuditLog
from apps.attendance.models import AttendanceRecord, OvertimeRecord, Shift
from apps.super_admin.models import OrganizationProfile
from apps.departments.models import Department
from django.utils import timezone
from datetime import date, time, timedelta

User = get_user_model()

class RoleBasedAccessControlTest(TestCase):
    def setUp(self):
        # 1. Create Super Admin
        self.super_admin = User.objects.create_superuser(username='superadmin', password='password123', email='sa@test.com')
        
        # 2. Create Admin
        self.admin = User.objects.create_user(username='admin', password='password123', email='admin@test.com', role='ADMIN')
        self.org = OrganizationProfile.objects.create(admin=self.admin, name="Test Org", enable_overtime=True)
        
        # Create Department
        self.department = Department.objects.create(name="Engineering", code="ENG")
        
        # 3. Create Shift
        self.shift = Shift.objects.create(
            admin=self.admin,
            name="General Shift",
            start_time=time(9, 0),
            end_time=time(17, 0)
        )
        
        # 4. Create Manager
        self.manager_user = User.objects.create_user(username='manager1', password='password123', email='manager@test.com', role='EMPLOYEE')
        self.manager_profile = EmployeeProfile.objects.create(
            user=self.manager_user,
            employee_id="EMP_MGR",
            employee_type="MANAGER",
            designation="Manager",
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=self.shift
        )
        
        # 5. Create HR
        self.hr_user = User.objects.create_user(username='hr1', password='password123', email='hr@test.com', role='EMPLOYEE')
        self.hr_profile = EmployeeProfile.objects.create(
            user=self.hr_user,
            employee_id="EMP_HR",
            employee_type="HR_TEAM",
            designation="HR Specialist",
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=self.shift
        )
        
        # 6. Create Employees
        self.emp1_user = User.objects.create_user(username='emp1', password='password123', email='emp1@test.com', role='EMPLOYEE')
        self.emp1_profile = EmployeeProfile.objects.create(
            user=self.emp1_user,
            employee_id="EMP_001",
            employee_type="EMPLOYEE",
            reporting_manager=self.manager_user,
            designation="Regular Employee",
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=self.shift
        )

        self.emp2_user = User.objects.create_user(username='emp2', password='password123', email='emp2@test.com', role='EMPLOYEE')
        self.emp2_profile = EmployeeProfile.objects.create(
            user=self.emp2_user,
            employee_id="EMP_002",
            employee_type="EMPLOYEE",
            designation="Regular Employee 2",
            date_of_joining=date.today(),
            created_by=self.admin,
            shift=self.shift
        )

        # Clients
        self.admin_client = Client()
        self.admin_client.login(username='admin', password='password123')
        
        self.hr_client = Client()
        self.hr_client.login(username='hr1', password='password123')
        
        self.manager_client = Client()
        self.manager_client.login(username='manager1', password='password123')

    def test_hr_can_create_employee_with_manager(self):
        # HR Team member can register new employees
        from apps.employee_management.forms import EmployeeAddForm
        
        # Form data: Employee type Employee without manager (should fail)
        form_data = {
            'username': 'newemp',
            'password': 'password123',
            'email': 'newemp@test.com',
            'first_name': 'New',
            'last_name': 'Employee',
            'employee_id': 'EMP_NEW',
            'employee_type': 'EMPLOYEE',
            'reporting_manager': '',
            'department': self.department.id,
            'gender': 'MALE',
            'designation': 'Staff',
            'date_of_joining': date.today(),
            'status': 'ACTIVE',
            'shift': self.shift.id
        }
        form = EmployeeAddForm(data=form_data, creator=self.hr_user)
        self.assertFalse(form.is_valid())
        self.assertIn('reporting_manager', form.errors)
        
        # Form data: Employee type Employee with manager (should pass validation)
        form_data['reporting_manager'] = self.manager_user.id
        form = EmployeeAddForm(data=form_data, creator=self.hr_user)
        self.assertTrue(form.is_valid())

    def test_manager_employee_list_filtering(self):
        # Manager employee list should only return employees reporting to them
        url = reverse('employee_management:employee_list')
        response = self.manager_client.get(url)
        self.assertEqual(response.status_code, 200)
        employees_in_context = response.context['employees']
        
        self.assertIn(self.emp1_profile, employees_in_context)
        self.assertNotIn(self.emp2_profile, employees_in_context)

    def test_manager_details_view_restriction(self):
        # Manager can view direct report details
        url = reverse('employee_management:employee_details', args=[self.emp1_profile.id])
        response = self.manager_client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Manager cannot view non-report details
        url = reverse('employee_management:employee_details', args=[self.emp2_profile.id])
        response = self.manager_client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_manager_can_edit_attendance_with_reason(self):
        # Create an attendance record for emp1
        record = AttendanceRecord.objects.create(
            user=self.emp1_user,
            date=date.today(),
            check_in=timezone.now() - timedelta(hours=8),
            check_out=timezone.now(),
            status='PRESENT'
        )
        
        url = reverse('attendance:edit_attendance_record', args=[record.id])
        
        post_data = {
            'check_in': (timezone.now() - timedelta(hours=7)).strftime('%Y-%m-%dT%H:%M'),
            'check_out': (timezone.now() + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M'),
            'status': 'PRESENT',
            'reason': 'Forgot to clock in on time'
        }
        response = self.manager_client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        
        # Check audit log
        audit = EmployeeTimingAuditLog.objects.filter(employee_profile=self.emp1_profile).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.reason, 'Forgot to clock in on time')
        self.assertEqual(audit.modified_by, self.manager_user)

    def test_manager_cannot_edit_unrelated_attendance(self):
        # Create an attendance record for emp2
        record = AttendanceRecord.objects.create(
            user=self.emp2_user,
            date=date.today(),
            check_in=timezone.now() - timedelta(hours=8),
            status='PRESENT'
        )
        
        url = reverse('attendance:edit_attendance_record', args=[record.id])
        
        post_data = {
            'check_in': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'status': 'PRESENT',
            'reason': 'Unauthorized edit attempt'
        }
        response = self.manager_client.post(url, post_data)
        self.assertEqual(response.status_code, 403)

    def test_manager_can_process_reportee_leaves(self):
        # Create leave request for emp1
        leave = LeaveRequest.objects.create(
            user=self.emp1_user,
            leave_type='SICK',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            reason='Medical recovery',
            status='PENDING'
        )
        
        url = reverse('leave_management:approve_leave', args=[leave.id])
        response = self.manager_client.post(url)
        self.assertEqual(response.status_code, 302)
        
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'APPROVED')
        self.assertEqual(leave.approved_by, self.manager_user)
        
        # Check leave approval audit log
        audit = LeaveApprovalAuditLog.objects.filter(leave_request=leave).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, 'APPROVED')
        self.assertEqual(audit.action_by, self.manager_user)

    def test_manager_cannot_process_unrelated_leaves(self):
        # Create leave request for emp2
        leave = LeaveRequest.objects.create(
            user=self.emp2_user,
            leave_type='SICK',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            reason='Medical recovery',
            status='PENDING'
        )
        
        url = reverse('leave_management:approve_leave', args=[leave.id])
        response = self.manager_client.post(url)
        self.assertEqual(response.status_code, 403)
