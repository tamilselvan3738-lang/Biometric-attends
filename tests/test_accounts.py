from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
import os

User = get_user_model()

class AccountsTestCase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            username='sadmin',
            email='sadmin@example.com',
            password='password123',
            role='SUPER_ADMIN'
        )
        self.admin = User.objects.create_user(
            username='admin1',
            email='admin1@example.com',
            password='password123',
            role='ADMIN'
        )
        self.employee = User.objects.create_user(
            username='emp1',
            email='emp1@example.com',
            password='password123',
            role='EMPLOYEE'
        )

    def test_user_creation_roles(self):
        self.assertEqual(self.superadmin.role, 'SUPER_ADMIN')
        self.assertEqual(self.admin.role, 'ADMIN')
        self.assertEqual(self.employee.role, 'EMPLOYEE')

    def test_profile_auto_creation(self):
        # User profile should be auto-created by signals
        self.assertIsNotNone(self.employee.userprofile)
        self.assertEqual(self.employee.userprofile.user, self.employee)

    def test_login_view(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'emp1',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302) # Redirect to dispatcher

    def test_login_prevention_for_terminated_employee(self):
        # Terminate employee
        self.employee.is_active = False
        self.employee.is_terminated = True
        self.employee.save()
        
        response = self.client.post(reverse('accounts:login'), {
            'username': 'emp1',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200) # Remain on login page
        messages = list(response.context['messages'])
        self.assertTrue(any("Your account has been terminated. Please contact your administrator for further assistance." in str(m) for m in messages))

    def test_login_prevention_for_terminated_admin(self):
        # Terminate admin
        self.admin.is_active = False
        self.admin.is_terminated = True
        self.admin.save()
        
        response = self.client.post(reverse('accounts:login'), {
            'username': 'admin1',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200) # Remain on login page
        messages = list(response.context['messages'])
        self.assertTrue(any("Your account has been terminated. Please contact the Super Administrator." in str(m) for m in messages))

    def test_middleware_kickout(self):
        # Log in employee
        self.client.login(username='emp1', password='password123')
        
        # Deactivate employee mid-session
        self.employee.is_active = False
        self.employee.is_terminated = True
        self.employee.save()
        
        # Access a dashboard page
        response = self.client.get(reverse('dashboards:dispatcher'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('accounts:login')))

    def test_permanent_deletion_cleanup(self):
        from apps.employee_management.models import EmployeeProfile
        from apps.super_admin.models import TerminatedAccount
        from apps.attendance.models import AttendanceRecord
        from apps.biometric.models import FaceEnrollment
        from apps.leave_management.models import LeaveRequest
        from django.utils import timezone
        
        # Create department
        from apps.departments.models import Department
        dept = Department.objects.create(name='Eng', code='ENG', manager=self.admin)
        
        # Create employee profile
        profile = EmployeeProfile.objects.create(
            user=self.employee,
            created_by=self.admin,
            department=dept,
            designation='Engineer',
            employee_id='EMP-001',
            date_of_joining=timezone.localdate(),
            status='ACTIVE'
        )
        
        # Create biometric templates, attendance records, leaves
        FaceEnrollment.objects.create(
            user=self.employee,
            face_data='{"templates": []}'
        )
        AttendanceRecord.objects.create(
            user=self.employee,
            check_in=timezone.now(),
            status='PRESENT'
        )
        LeaveRequest.objects.create(
            user=self.employee,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            status='APPROVED',
            reason='test'
        )
        
        # Terminate them
        TerminatedAccount.objects.create(username='emp1', role='EMPLOYEE')
        
        # Perform deletion request
        self.client.login(username='admin1', password='password123')
        response = self.client.post(reverse('employee_management:delete_employee', args=[profile.pk]))
        self.assertEqual(response.status_code, 302)
        
        # Assert they are fully cleaned up
        self.assertFalse(User.objects.filter(username='emp1').exists())
        self.assertFalse(EmployeeProfile.objects.filter(pk=profile.pk).exists())
        self.assertFalse(FaceEnrollment.objects.filter(user=self.employee).exists())
        self.assertFalse(AttendanceRecord.objects.filter(user=self.employee).exists())
        self.assertFalse(LeaveRequest.objects.filter(user=self.employee).exists())
        self.assertFalse(TerminatedAccount.objects.filter(username='emp1').exists())
        
        # Assert username can be reused
        new_emp = User.objects.create_user(
            username='emp1',
            email='newemp@example.com',
            password='password123',
            role='EMPLOYEE'
        )
        self.assertEqual(new_emp.username, 'emp1')

    def test_gender_and_dob_fields(self):
        # Default gender MALE
        self.assertEqual(self.employee.gender, 'MALE')
        self.assertIsNone(self.employee.date_of_birth)
        
        # Modify gender and DOB
        self.employee.gender = 'FEMALE'
        import datetime
        self.employee.date_of_birth = datetime.date(1995, 5, 10)
        self.employee.save()
        
        updated_emp = User.objects.get(pk=self.employee.pk)
        self.assertEqual(updated_emp.gender, 'FEMALE')
        self.assertEqual(updated_emp.date_of_birth, datetime.date(1995, 5, 10))

    def test_employee_dashboard_profile_update(self):
        from apps.employee_management.models import EmployeeProfile
        from apps.departments.models import Department
        import datetime
        
        dept = Department.objects.create(name='Eng', code='ENG', manager=self.admin)
        profile = EmployeeProfile.objects.create(
            user=self.employee,
            created_by=self.admin,
            department=dept,
            designation='Engineer',
            employee_id='EMP-001',
            date_of_joining=datetime.date.today(),
            status='ACTIVE'
        )
        
        self.client.login(username='emp1', password='password123')
        
        response = self.client.post(reverse('dashboards:employee_dashboard'), {
            'first_name': 'NewFirst',
            'last_name': 'NewLast',
            'email': 'newemail@example.com',
            'phone_number': '9876543210',
            'gender': 'FEMALE',
            'date_of_birth': '1995-05-10',
            'bio': 'A brief bio info.',
            'address': '123 Main St'
        })
        # Check redirect to employee dashboard
        self.assertEqual(response.status_code, 302)
        
        # Verify changes propagated
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.first_name, 'NewFirst')
        self.assertEqual(self.employee.last_name, 'NewLast')
        self.assertEqual(self.employee.email, 'newemail@example.com')
        self.assertEqual(self.employee.phone_number, '9876543210')
        self.assertEqual(self.employee.gender, 'FEMALE')
        self.assertEqual(self.employee.date_of_birth, datetime.date(1995, 5, 10))
        
        profile.refresh_from_db()
        self.assertEqual(self.employee.userprofile.bio, 'A brief bio info.')
        self.assertEqual(self.employee.userprofile.address, '123 Main St')

    def test_employee_profile_avatar_sync(self):
        from apps.employee_management.models import EmployeeProfile
        from apps.departments.models import Department
        from django.core.files.uploadedfile import SimpleUploadedFile
        import io
        from PIL import Image
        import datetime
        
        dept = Department.objects.create(name='Eng', code='ENG', manager=self.admin)
        profile = EmployeeProfile.objects.create(
            user=self.employee,
            created_by=self.admin,
            department=dept,
            designation='Engineer',
            employee_id='EMP-001',
            date_of_joining=datetime.date.today(),
            status='ACTIVE'
        )
        
        # Create dummy image
        file = io.BytesIO()
        image = Image.new('RGB', size=(100, 100), color=(255, 0, 0))
        image.save(file, 'png')
        file.name = 'test_avatar.png'
        file.seek(0)
        uploaded_image = SimpleUploadedFile(file.name, file.read(), content_type='image/png')
        
        self.client.login(username='emp1', password='password123')
        
        response = self.client.post(reverse('dashboards:employee_dashboard'), {
            'first_name': 'NewFirst',
            'last_name': 'NewLast',
            'email': 'newemail@example.com',
            'phone_number': '9876543210',
            'gender': 'MALE',
            'date_of_birth': '1995-05-10',
            'avatar': uploaded_image,
            'bio': 'A brief bio info.',
            'address': '123 Main St'
        })
        self.assertEqual(response.status_code, 302)
        
        profile.refresh_from_db()
        self.assertTrue(profile.profile_image.name.endswith('.png'))
        
        # Cleanup
        try:
            if profile.profile_image and os.path.exists(profile.profile_image.path):
                os.remove(profile.profile_image.path)
            if self.employee.userprofile.avatar and os.path.exists(self.employee.userprofile.avatar.path):
                os.remove(self.employee.userprofile.avatar.path)
        except Exception:
            pass
