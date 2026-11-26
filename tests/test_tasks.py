from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from datetime import date, timedelta
from apps.tasks.models import Task, TaskAssignment, TaskAttachment, TaskComment, TaskAuditLog
from apps.employee_management.models import EmployeeProfile
from apps.departments.models import Department
from apps.super_admin.models import OrganizationProfile

User = get_user_model()

class TaskManagementSystemTest(TestCase):
    def setUp(self):
        # Create Admin
        self.admin = User.objects.create_user(username='org_admin', password='password123', role='ADMIN')
        self.org_profile = OrganizationProfile.objects.create(
            admin=self.admin,
            name="Test Org",
            enable_overtime=True,
            enable_employee_types=True
        )
        
        # Create Manager
        self.manager = User.objects.create_user(username='manager1', password='password123', role='EMPLOYEE')
        self.dept = Department.objects.create(name="Engineering", code="ENG")
        self.manager_profile = EmployeeProfile.objects.create(
            user=self.manager,
            employee_id='MGR001',
            employee_type='MANAGER',
            designation='Lead Eng',
            date_of_joining=date.today(),
            created_by=self.admin
        )
        
        # Create Direct Report Employee
        self.employee = User.objects.create_user(username='emp_direct', password='password123', role='EMPLOYEE')
        self.employee_profile = EmployeeProfile.objects.create(
            user=self.employee,
            employee_id='EMP001',
            employee_type='EMPLOYEE',
            reporting_manager=self.manager,
            designation='Engineer',
            date_of_joining=date.today(),
            created_by=self.admin
        )

        # Create Another Manager & Another Employee (Not reporting to manager1)
        self.other_manager = User.objects.create_user(username='manager2', password='password123', role='EMPLOYEE')
        self.other_manager_profile = EmployeeProfile.objects.create(
            user=self.other_manager,
            employee_id='MGR002',
            employee_type='MANAGER',
            designation='Lead Eng 2',
            date_of_joining=date.today(),
            created_by=self.admin
        )
        self.other_employee = User.objects.create_user(username='emp_other', password='password123', role='EMPLOYEE')
        self.other_employee_profile = EmployeeProfile.objects.create(
            user=self.other_employee,
            employee_id='EMP002',
            employee_type='EMPLOYEE',
            reporting_manager=self.other_manager,
            designation='Engineer 2',
            date_of_joining=date.today(),
            created_by=self.admin
        )

        self.client = Client()

    def test_manager_task_creation_and_reporting_employees_restriction(self):
        self.client.force_login(self.manager)
        
        # 1. Successful creation with direct reporting employee
        url = reverse('tasks:manager_task_create')
        response = self.client.post(url, {
            'title': 'Build Feature X',
            'description': 'Develop the task manager backend modules.',
            'priority': 'HIGH',
            'start_date': date.today(),
            'due_date': date.today() + timedelta(days=5),
            'assigned_employees': [self.employee.pk]
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify task is created
        task = Task.objects.filter(title='Build Feature X').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.created_by, self.manager)
        
        # Verify assignment is created
        assignment = TaskAssignment.objects.filter(task=task, employee=self.employee).first()
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.status, 'NOT_STARTED')

        # Verify audit logs created
        self.assertTrue(TaskAuditLog.objects.filter(task_name=task.title, action_performed='Task Creation').exists())
        self.assertTrue(TaskAuditLog.objects.filter(task_name=task.title, action_performed='Task Assignment').exists())

        # 2. Attempt to assign task to an employee who does NOT report to this manager
        # The form queryset validation will prevent it, but if a POST request bypasses form filters, views raise PermissionDenied
        response_unauthorized = self.client.post(url, {
            'title': 'Rogue Task',
            'description': 'Assigning to an unauthorized employee.',
            'priority': 'LOW',
            'start_date': date.today(),
            'due_date': date.today() + timedelta(days=2),
            'assigned_employees': [self.other_employee.pk]
        })
        # If bypass was attempted, the form validation should catch it (field validation error because querysets do not contain other_employee)
        # or view raising PermissionDenied.
        # In our case, the form won't be valid since other_employee is not in queryset, rendering 200 with form errors.
        self.assertEqual(response_unauthorized.status_code, 200)
        self.assertFormError(response_unauthorized, 'form', 'assigned_employees', 
                             f'Select a valid choice. {self.other_employee.pk} is not one of the available choices.')

    def test_employee_view_and_status_update_workflow(self):
        # Manager creates a task first
        task = Task.objects.create(
            title='Fix Bug Y',
            description='Fix UI alignment error.',
            priority='MEDIUM',
            start_date=date.today(),
            due_date=date.today() + timedelta(days=2),
            created_by=self.manager
        )
        assignment = TaskAssignment.objects.create(task=task, employee=self.employee, status='NOT_STARTED')

        # Log in as employee
        self.client.force_login(self.employee)
        
        # View assigned tasks list
        url_list = reverse('tasks:employee_task_list')
        response_list = self.client.get(url_list)
        self.assertEqual(response_list.status_code, 200)
        self.assertContains(response_list, 'Fix Bug Y')

        # View task detail
        url_detail = reverse('tasks:employee_task_detail', args=[assignment.pk])
        response_detail = self.client.get(url_detail)
        self.assertEqual(response_detail.status_code, 200)

        # Update status to IN_PROGRESS
        response_update = self.client.post(url_detail, {
            'status_submit': '1',
            'status': 'IN_PROGRESS',
            'comment': 'Starting UI refactoring now.'
        })
        self.assertEqual(response_update.status_code, 302)
        
        # Verify status and comments updated
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'IN_PROGRESS')
        self.assertTrue(TaskComment.objects.filter(task=task, author=self.employee, content='Starting UI refactoring now.').exists())

        # Verify audit logs for status change and comment
        self.assertTrue(TaskAuditLog.objects.filter(task_name=task.title, action_performed='Status Changes').exists())

    def test_manager_completion_acceptance_and_rework_workflow(self):
        # Setup task assigned to employee
        task = Task.objects.create(
            title='Code Review',
            description='Review PR #23.',
            priority='LOW',
            start_date=date.today(),
            due_date=date.today() + timedelta(days=3),
            created_by=self.manager
        )
        assignment = TaskAssignment.objects.create(task=task, employee=self.employee, status='IN_PROGRESS')

        # Employee marks task as COMPLETED
        self.client.force_login(self.employee)
        url_emp_detail = reverse('tasks:employee_task_detail', args=[assignment.pk])
        self.client.post(url_emp_detail, {
            'status_submit': '1',
            'status': 'COMPLETED',
            'comment': 'All checks passed. Ready for approval.'
        })
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'COMPLETED')

        # Manager requests rework
        self.client.force_login(self.manager)
        url_mgr_detail = reverse('tasks:manager_task_detail', args=[task.pk])
        
        # Rework submit requires comments
        response_rework_err = self.client.post(url_mgr_detail, {
            'assignment_id': assignment.pk,
            'action': 'rework',
            'rework_comments': '' # Empty comments
        })
        self.assertEqual(response_rework_err.status_code, 302) # Redirects with error message
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'COMPLETED') # Status did not change

        response_rework = self.client.post(url_mgr_detail, {
            'assignment_id': assignment.pk,
            'action': 'rework',
            'rework_comments': 'Please check style constraints and re-verify.'
        })
        self.assertEqual(response_rework.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'REWORK')
        
        # Verify comment created
        self.assertTrue(TaskComment.objects.filter(task=task, author=self.manager, content='[REWORK REQUESTED] Please check style constraints and re-verify.').exists())

        # Employee marks it as COMPLETED again
        self.client.force_login(self.employee)
        self.client.post(url_emp_detail, {
            'status_submit': '1',
            'status': 'COMPLETED',
            'comment': 'Refactored styles.'
        })
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'COMPLETED')

        # Manager approves
        self.client.force_login(self.manager)
        response_approve = self.client.post(url_mgr_detail, {
            'assignment_id': assignment.pk,
            'action': 'accept'
        })
        self.assertEqual(response_approve.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'APPROVED')

    def test_task_export_endpoints(self):
        self.client.force_login(self.manager)
        
        # Export PDF
        pdf_url = reverse('tasks:export_tasks_pdf')
        pdf_response = self.client.get(pdf_url)
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response['Content-Type'], 'application/pdf')
        
        # Export Excel/CSV
        csv_url = reverse('tasks:export_tasks_excel')
        csv_response = self.client.get(csv_url)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(csv_response['Content-Type'], 'text/csv')

    def test_admin_task_assignment_when_employee_types_disabled(self):
        # 1. Disable employee types organization-wide
        self.org_profile.enable_employee_types = False
        self.org_profile.save()
        
        # 2. Verify Manager is denied access
        self.client.force_login(self.manager)
        url_create = reverse('tasks:manager_task_create')
        response_mgr = self.client.get(url_create)
        self.assertEqual(response_mgr.status_code, 302) # Redirect due to Access Denied
        
        # 3. Log in as Admin (should be allowed)
        self.client.force_login(self.admin)
        response_admin_get = self.client.get(url_create)
        self.assertEqual(response_admin_get.status_code, 200)

        # 4. Create and Assign task to both employee and other_employee
        response_admin_post = self.client.post(url_create, {
            'title': 'Admin Directive 1',
            'description': 'Organization-wide review task.',
            'priority': 'CRITICAL',
            'start_date': date.today(),
            'due_date': date.today() + timedelta(days=3),
            'assigned_employees': [self.employee.pk, self.other_employee.pk]
        })
        self.assertEqual(response_admin_post.status_code, 302)
        
        # Verify task is created
        task = Task.objects.filter(title='Admin Directive 1').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.created_by, self.admin)
        
        # Verify both assignments exist
        a1 = TaskAssignment.objects.filter(task=task, employee=self.employee).first()
        a2 = TaskAssignment.objects.filter(task=task, employee=self.other_employee).first()
        self.assertIsNotNone(a1)
        self.assertIsNotNone(a2)
        
        # Verify Audit Log role is recorded as 'Admin'
        log = TaskAuditLog.objects.filter(task_name=task.title, action_performed='Task Creation').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_role, 'Admin')
        
        # 5. Verify Employee updates task status
        self.client.force_login(self.employee)
        url_emp_detail = reverse('tasks:employee_task_detail', args=[a1.pk])
        self.client.post(url_emp_detail, {
            'status_submit': '1',
            'status': 'COMPLETED',
            'comment': 'Done with my part.'
        })
        a1.refresh_from_db()
        self.assertEqual(a1.status, 'COMPLETED')
        
        # Verify Admin receives notification and can accept completion
        self.client.force_login(self.admin)
        url_mgr_detail = reverse('tasks:manager_task_detail', args=[task.pk])
        response_accept = self.client.post(url_mgr_detail, {
            'assignment_id': a1.pk,
            'action': 'accept'
        })
        self.assertEqual(response_accept.status_code, 302)
        a1.refresh_from_db()
        self.assertEqual(a1.status, 'APPROVED')
        
        # Verify Audit Log for acceptance recorded as 'Admin'
        log_accept = TaskAuditLog.objects.filter(task_name=task.title, action_performed='Completion Accepted').first()
        self.assertIsNotNone(log_accept)
        self.assertEqual(log_accept.user_role, 'Admin')

        # 6. Verify Admin can export reports
        pdf_url = reverse('tasks:export_tasks_pdf')
        pdf_response = self.client.get(pdf_url)
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response['Content-Type'], 'application/pdf')
