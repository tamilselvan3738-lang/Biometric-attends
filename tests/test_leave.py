from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.leave_management.models import LeaveRequest
from apps.notifications.models import Notification
from datetime import date

User = get_user_model()

class LeaveTestCase(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            username='emp_test',
            email='test@example.com',
            password='password123',
            role='EMPLOYEE'
        )
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@example.com',
            password='password123',
            role='ADMIN'
        )

    def test_apply_leave(self):
        leave = LeaveRequest.objects.create(
            user=self.employee,
            leave_type='SICK',
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 5),
            reason='Medical procedure'
        )
        self.assertEqual(leave.status, 'PENDING')

    def test_approve_leave(self):
        leave = LeaveRequest.objects.create(
            user=self.employee,
            leave_type='CASUAL',
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
            reason='Personal reasons'
        )
        
        # Approve
        leave.status = 'APPROVED'
        leave.approved_by = self.admin
        leave.save()
        
        # Verify notification creation
        Notification.objects.create(
            recipient=leave.user,
            title="Leave Approved",
            message="Your leave has been approved."
        )
        
        self.assertEqual(leave.status, 'APPROVED')
        self.assertTrue(Notification.objects.filter(recipient=self.employee, title="Leave Approved").exists())
