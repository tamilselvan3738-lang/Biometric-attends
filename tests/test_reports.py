from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.attendance.models import AttendanceRecord
from django.urls import reverse

User = get_user_model()

class ReportsTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_rep',
            email='admin@example.com',
            password='password123',
            role='ADMIN'
        )
        self.employee = User.objects.create_user(
            username='emp_rep',
            email='emp@example.com',
            password='password123',
            role='EMPLOYEE'
        )

    def test_unauthorized_user_blocked_from_corporate_report(self):
        self.client.login(username='emp_rep', password='password123')
        response = self.client.get(reverse('reports:attendance_report'))
        # Should redirect to dashboard dispatcher because of decorators
        self.assertEqual(response.status_code, 302)

    def test_authorized_user_allowed_on_corporate_report(self):
        self.client.login(username='admin_rep', password='password123')
        response = self.client.get(reverse('reports:attendance_report'))
        self.assertEqual(response.status_code, 200)
