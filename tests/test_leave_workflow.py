from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.employee_management.models import EmployeeProfile
from apps.leave_management.models import LeaveRequest, LeaveApprovalAuditLog
from apps.notifications.models import Notification
from apps.super_admin.models import OrganizationProfile
from apps.attendance.models import Shift
from datetime import date, time, timedelta

User = get_user_model()

class LeaveApprovalWorkflowTest(TestCase):
    def setUp(self):
        # 1. Create Admin
        self.admin = User.objects.create_user(username='admin', password='password123', email='admin@test.com', role='ADMIN')
        self.org = OrganizationProfile.objects.create(admin=self.admin, name="Test Org", enable_overtime=True)
        
        # 2. Create Shift
        self.shift = Shift.objects.create(
            admin=self.admin,
            name="General Shift",
            start_time=time(9, 0),
            end_time=time(17, 0)
        )
        
        # 3. Create Manager
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
        
        # 4. Create HR
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
        
        # 5. Create Employee under Manager
        self.emp_user = User.objects.create_user(username='emp1', password='password123', email='emp1@test.com', role='EMPLOYEE')
        self.emp_profile = EmployeeProfile.objects.create(
            user=self.emp_user,
            employee_id="EMP_001",
            employee_type="EMPLOYEE",
            reporting_manager=self.manager_user,
            designation="Regular Employee",
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
        
        self.emp_client = Client()
        self.emp_client.login(username='emp1', password='password123')

    def test_employee_leave_routes_to_reporting_manager(self):
        Notification.objects.all().delete()
        
        # Apply for leave as regular Employee
        response = self.emp_client.post(reverse('leave_management:apply_leave'), {
            'leave_type': 'SICK',
            'start_date': date.today() + timedelta(days=2),
            'end_date': date.today() + timedelta(days=5),
            'reason': 'Medical emergency'
        })
        
        # Check redirect
        self.assertEqual(response.status_code, 302)
        
        # Check leave request was created
        leave = LeaveRequest.objects.get(user=self.emp_user)
        self.assertEqual(leave.status, 'PENDING')
        
        # Check Notification was created for the Reporting Manager
        notifications = Notification.objects.filter(recipient=self.manager_user)
        self.assertEqual(notifications.count(), 1)
        self.assertIn("Medical emergency", notifications[0].message or "")

    def test_hr_leave_routes_to_admin(self):
        Notification.objects.all().delete()
        
        # Apply for leave as HR Team member
        response = self.hr_client.post(reverse('leave_management:apply_leave'), {
            'leave_type': 'CASUAL',
            'start_date': date.today() + timedelta(days=2),
            'end_date': date.today() + timedelta(days=5),
            'reason': 'Personal work'
        })
        
        self.assertEqual(response.status_code, 302)
        leave = LeaveRequest.objects.get(user=self.hr_user)
        self.assertEqual(leave.status, 'PENDING')
        
        # Notification should go to Admin (created_by)
        notifications = Notification.objects.filter(recipient=self.admin)
        self.assertEqual(notifications.count(), 1)

    def test_manager_leave_routes_to_admin(self):
        Notification.objects.all().delete()
        
        # Apply for leave as Manager
        response = self.manager_client.post(reverse('leave_management:apply_leave'), {
            'leave_type': 'ANNUAL',
            'start_date': date.today() + timedelta(days=2),
            'end_date': date.today() + timedelta(days=5),
            'reason': 'Family vacation'
        })
        
        self.assertEqual(response.status_code, 302)
        leave = LeaveRequest.objects.get(user=self.manager_user)
        self.assertEqual(leave.status, 'PENDING')
        
        # Notification should go to Admin
        notifications = Notification.objects.filter(recipient=self.admin)
        self.assertEqual(notifications.count(), 1)

    def test_leave_requests_visibility(self):
        # Create leave requests for Employee, HR, and Manager
        emp_leave = LeaveRequest.objects.create(
            user=self.emp_user, leave_type='SICK',
            start_date=date.today() + timedelta(days=2), end_date=date.today() + timedelta(days=5),
            reason='Sick', status='PENDING'
        )
        hr_leave = LeaveRequest.objects.create(
            user=self.hr_user, leave_type='CASUAL',
            start_date=date.today() + timedelta(days=2), end_date=date.today() + timedelta(days=5),
            reason='Casual', status='PENDING'
        )
        mgr_leave = LeaveRequest.objects.create(
            user=self.manager_user, leave_type='ANNUAL',
            start_date=date.today() + timedelta(days=2), end_date=date.today() + timedelta(days=5),
            reason='Vacation', status='PENDING'
        )
        
        # Admin requests list view:
        # Admin should see HR and Manager leaves, but NOT Employee leaves
        response = self.admin_client.get(reverse('leave_management:leave_requests'))
        self.assertEqual(response.status_code, 200)
        pending_leaves_admin = response.context['pending_leaves']
        self.assertIn(hr_leave, pending_leaves_admin)
        self.assertIn(mgr_leave, pending_leaves_admin)
        self.assertNotIn(emp_leave, pending_leaves_admin)
        
        # Manager requests list view:
        # Manager should see Employee leaves, but NOT HR or Manager leaves
        response = self.manager_client.get(reverse('leave_management:leave_requests'))
        self.assertEqual(response.status_code, 200)
        pending_leaves_mgr = response.context['pending_leaves']
        self.assertIn(emp_leave, pending_leaves_mgr)
        self.assertNotIn(hr_leave, pending_leaves_mgr)
        self.assertNotIn(mgr_leave, pending_leaves_mgr)

    def test_approve_leave_with_remarks_and_audit(self):
        emp_leave = LeaveRequest.objects.create(
            user=self.emp_user, leave_type='SICK',
            start_date=date.today() + timedelta(days=2), end_date=date.today() + timedelta(days=5),
            reason='Sick', status='PENDING'
        )
        
        # Try approving as Admin (unauthorized, employee must be approved by reporting manager)
        response = self.admin_client.post(reverse('leave_management:approve_leave', args=[emp_leave.pk]), {
            'remarks': 'Approved by admin'
        })
        self.assertEqual(response.status_code, 403)
        
        # Approve as Manager (authorized)
        Notification.objects.all().delete()
        response = self.manager_client.post(reverse('leave_management:approve_leave', args=[emp_leave.pk]), {
            'remarks': 'Take care, approved.'
        })
        self.assertEqual(response.status_code, 302)
        
        emp_leave.refresh_from_db()
        self.assertEqual(emp_leave.status, 'APPROVED')
        self.assertEqual(emp_leave.remarks, 'Take care, approved.')
        self.assertEqual(emp_leave.approved_by, self.manager_user)
        
        # Audit log verification
        audit = LeaveApprovalAuditLog.objects.filter(leave_request=emp_leave, action='APPROVED')
        self.assertEqual(audit.count(), 1)
        self.assertEqual(audit[0].remarks, 'Take care, approved.')
        self.assertEqual(audit[0].action_by, self.manager_user)
        
        # Notification verification: Employee should be notified
        notifications = Notification.objects.filter(recipient=self.emp_user)
        self.assertEqual(notifications.count(), 1)
        self.assertIn("Take care, approved.", notifications[0].message)

    def test_leave_details_security_permissions(self):
        emp_leave = LeaveRequest.objects.create(
            user=self.emp_user, leave_type='SICK',
            start_date=date.today() + timedelta(days=2), end_date=date.today() + timedelta(days=5),
            reason='Sick', status='PENDING'
        )
        hr_leave = LeaveRequest.objects.create(
            user=self.hr_user, leave_type='CASUAL',
            start_date=date.today() + timedelta(days=2), end_date=date.today() + timedelta(days=5),
            reason='Casual', status='PENDING'
        )
        
        # Employee tries to view HR leave details (unauthorized)
        response = self.emp_client.get(reverse('leave_management:leave_details', args=[hr_leave.pk]))
        self.assertEqual(response.status_code, 403)
        
        # Employee views their own leave details (authorized)
        response = self.emp_client.get(reverse('leave_management:leave_details', args=[emp_leave.pk]))
        self.assertEqual(response.status_code, 200)
        
        # Admin views employee leave details (unauthorized by matrix)
        response = self.admin_client.get(reverse('leave_management:leave_details', args=[emp_leave.pk]))
        self.assertEqual(response.status_code, 403)
        
        # Admin views HR leave details (authorized)
        response = self.admin_client.get(reverse('leave_details', args=[hr_leave.pk]) if False else reverse('leave_management:leave_details', args=[hr_leave.pk]))
        self.assertEqual(response.status_code, 200)
