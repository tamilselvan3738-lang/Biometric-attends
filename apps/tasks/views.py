import json
import csv
import io
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, Http404, JsonResponse
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from apps.accounts.permissions import employee_required
from apps.notifications.models import Notification
from .models import Task, TaskAssignment, TaskAttachment, TaskComment, TaskAuditLog
from .forms import TaskCreateForm, TaskUpdateForm, EmployeeTaskUpdateForm, TaskCommentForm

User = get_user_model()

# Custom Permission Decorators
def task_authority_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
            
        enable_employee_types = True
        if request.user.role == 'ADMIN':
            admin_user = request.user
        else:
            admin_user = request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None
            
        if admin_user:
            try:
                enable_employee_types = admin_user.organization.enable_employee_types
            except Exception:
                pass
                
        if (enable_employee_types and request.user.is_manager) or (not enable_employee_types and request.user.role == 'ADMIN'):
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "Access Denied: You do not have task assignment authority.")
            return redirect('dashboards:dispatcher')
    return _wrapped_view

def regular_employee_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.role == 'EMPLOYEE' and not request.user.is_hr and not request.user.is_manager:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "Access Denied: Regular Employee permission required.")
            return redirect('dashboards:dispatcher')
    return _wrapped_view


# --- TASK AUTHORITY VIEWS ---

@login_required
@task_authority_required
def manager_task_list(request):
    today = date.today()
    tasks = Task.objects.filter(created_by=request.user).order_by('-created_at')
    
    # Calculate Summary Statistics
    total_tasks = tasks.count()
    
    pending_tasks = TaskAssignment.objects.filter(
        task__created_by=request.user,
        status__in=['NOT_STARTED', 'ON_HOLD', 'REWORK'],
        task__is_cancelled=False
    ).count()
    
    in_progress_tasks = TaskAssignment.objects.filter(
        task__created_by=request.user,
        status='IN_PROGRESS',
        task__is_cancelled=False
    ).count()
    
    completed_tasks = TaskAssignment.objects.filter(
        task__created_by=request.user,
        status='APPROVED'
    ).count()
    
    overdue_tasks = TaskAssignment.objects.filter(
        task__created_by=request.user,
        task__due_date__lt=today,
        task__is_cancelled=False
    ).exclude(status='APPROVED').count()

    upcoming_tasks = TaskAssignment.objects.filter(
        task__created_by=request.user,
        task__due_date__gte=today,
        task__due_date__lte=timezone.now().date() + timezone.timedelta(days=7),
        task__is_cancelled=False
    ).exclude(status='APPROVED').select_related('task', 'employee').order_by('task__due_date')

    # Resolve enable_employee_types
    enable_employee_types = True
    if request.user.role == 'ADMIN':
        admin_user = request.user
    else:
        admin_user = request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None
        
    if admin_user:
        try:
            enable_employee_types = admin_user.organization.enable_employee_types
        except Exception:
            pass

    if not enable_employee_types:
        reporting_employees = User.objects.filter(
            role='EMPLOYEE',
            employeeprofile__created_by=admin_user,
            employeeprofile__status='ACTIVE'
        )
    else:
        reporting_employees = User.objects.filter(
            role='EMPLOYEE',
            employeeprofile__reporting_manager=request.user,
            employeeprofile__status='ACTIVE'
        )
    
    performance_list = []
    for emp in reporting_employees:
        emp_assignments = TaskAssignment.objects.filter(employee=emp, task__is_cancelled=False)
        emp_total = emp_assignments.count()
        emp_done = emp_assignments.filter(status='APPROVED').count()
        emp_pending = emp_assignments.filter(status__in=['NOT_STARTED', 'IN_PROGRESS', 'ON_HOLD', 'REWORK']).count()
        emp_overdue = emp_assignments.filter(task__due_date__lt=today).exclude(status='APPROVED').count()
        rate = int((emp_done / emp_total) * 100) if emp_total > 0 else 0
        performance_list.append({
            'employee': emp,
            'total': emp_total,
            'completed': emp_done,
            'pending': emp_pending,
            'overdue': emp_overdue,
            'rate': rate
        })

    context = {
        'tasks': tasks,
        'total_tasks': total_tasks,
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'upcoming_tasks': upcoming_tasks,
        'performance_list': performance_list,
    }
    return render(request, 'tasks/manager_task_list.html', context)


@login_required
@task_authority_required
def manager_task_create(request):
    form = TaskCreateForm(request.POST or None, request.FILES or None, creator=request.user)
    if request.method == 'POST':
        if form.is_valid():
            # Resolve enable_employee_types & role string
            enable_employee_types = True
            if request.user.role == 'ADMIN':
                admin_user = request.user
                user_role = 'Admin'
            else:
                admin_user = request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None
                user_role = 'Manager'
                
            if admin_user:
                try:
                    enable_employee_types = admin_user.organization.enable_employee_types
                except Exception:
                    pass

            task = form.save(commit=False)
            task.created_by = request.user
            task.save()

            # Audit Log Creation
            TaskAuditLog.objects.create(
                username=request.user.username,
                user_role=user_role,
                task_name=task.title,
                action_performed='Task Creation',
                previous_value=None,
                updated_value=task.title
            )

            # Create Assignments
            assigned_employees = form.cleaned_data['assigned_employees']
            for emp in assigned_employees:
                # Security Rule: Verify assignee reporting structure
                if enable_employee_types:
                    if emp.employeeprofile.reporting_manager != request.user:
                        task.delete()
                        raise PermissionDenied("Cannot assign tasks to non-reporting employees.")
                else:
                    if emp.employeeprofile.created_by != request.user:
                        task.delete()
                        raise PermissionDenied("Cannot assign tasks to employees outside your organization.")
                
                TaskAssignment.objects.create(task=task, employee=emp, status='NOT_STARTED')
                
                # Audit Log Assignment
                TaskAuditLog.objects.create(
                    username=request.user.username,
                    user_role=user_role,
                    task_name=task.title,
                    action_performed='Task Assignment',
                    previous_value=None,
                    updated_value=f"Assigned to {emp.username}"
                )

                # Send Notification to Employee
                Notification.objects.create(
                    recipient=emp,
                    title="New Task Assigned",
                    message=f"{user_role} {request.user.username} has assigned you a new task: '{task.title}'."
                )

            # Handle Attachments
            files = request.FILES.getlist('files')
            for f in files:
                attachment = TaskAttachment.objects.create(task=task, uploaded_by=request.user, file=f, filename=f.name)
                # Audit Log File Upload
                TaskAuditLog.objects.create(
                    username=request.user.username,
                    user_role=user_role,
                    task_name=task.title,
                    action_performed='File Upload',
                    previous_value=None,
                    updated_value=f.name
                )

            messages.success(request, f"Task '{task.title}' has been successfully created and assigned.")
            return redirect('tasks:manager_task_list')

    return render(request, 'tasks/manager_task_form.html', {'form': form, 'title': 'Create New Task'})


@login_required
@task_authority_required
def manager_task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, created_by=request.user)
    
    if task.assignments.filter(status='APPROVED').exists():
        messages.error(request, "Completed tasks cannot be updated.")
        return redirect('tasks:manager_task_list')
    if task.is_cancelled:
        messages.error(request, "Cancelled tasks cannot be updated.")
        return redirect('tasks:manager_task_list')

    form = TaskUpdateForm(request.POST or None, request.FILES or None, instance=task, creator=request.user)
    if request.method == 'POST':
        if form.is_valid():
            # Resolve role and settings
            enable_employee_types = True
            if request.user.role == 'ADMIN':
                admin_user = request.user
                user_role = 'Admin'
            else:
                admin_user = request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None
                user_role = 'Manager'
                
            if admin_user:
                try:
                    enable_employee_types = admin_user.organization.enable_employee_types
                except Exception:
                    pass

            old_title = task.title
            task = form.save()

            # Audit Log Update
            TaskAuditLog.objects.create(
                username=request.user.username,
                user_role=user_role,
                task_name=task.title,
                action_performed='Task Updates',
                previous_value=old_title,
                updated_value=task.title
            )

            # Reassignment / Reallocation Logic
            new_assignees = form.cleaned_data['assigned_employees']
            current_assignments = {a.employee_id: a for a in task.assignments.all()}
            new_assignees_pks = [emp.pk for emp in new_assignees]
            
            # Remove deselected assignees
            for emp_id, assignment in current_assignments.items():
                if emp_id not in new_assignees_pks:
                    assignment.delete()
                    # Audit Log Reassignment
                    TaskAuditLog.objects.create(
                        username=request.user.username,
                        user_role=user_role,
                        task_name=task.title,
                        action_performed='Task Reassignment',
                        previous_value=f"Assigned to {assignment.employee.username}",
                        updated_value="Removed Assignment"
                    )
            
            # Add newly selected assignees
            for emp in new_assignees:
                if emp.pk not in current_assignments:
                    if enable_employee_types:
                        if emp.employeeprofile.reporting_manager != request.user:
                            raise PermissionDenied("Cannot assign tasks to non-reporting employees.")
                    else:
                        if emp.employeeprofile.created_by != request.user:
                            raise PermissionDenied("Cannot assign tasks to employees outside your organization.")
                            
                    TaskAssignment.objects.create(task=task, employee=emp, status='NOT_STARTED')
                    # Audit Log Reassignment
                    TaskAuditLog.objects.create(
                        username=request.user.username,
                        user_role=user_role,
                        task_name=task.title,
                        action_performed='Task Reassignment',
                        previous_value=None,
                        updated_value=f"Assigned to {emp.username}"
                    )
                    # Notify employee
                    Notification.objects.create(
                        recipient=emp,
                        title="New Task Assigned",
                        message=f"{user_role} {request.user.username} has assigned you a task: '{task.title}'."
                    )

            # Handle attachments
            files = request.FILES.getlist('files')
            for f in files:
                attachment = TaskAttachment.objects.create(task=task, uploaded_by=request.user, file=f, filename=f.name)
                # Audit Log File Upload
                TaskAuditLog.objects.create(
                    username=request.user.username,
                    user_role=user_role,
                    task_name=task.title,
                    action_performed='File Upload',
                    previous_value=None,
                    updated_value=f.name
                )

            # Notify existing/remaining assignees
            for assignment in task.assignments.all():
                Notification.objects.create(
                    recipient=assignment.employee,
                    title="Task Details Updated",
                    message=f"{user_role} {request.user.username} has updated details for task: '{task.title}'."
                )

            messages.success(request, f"Task '{task.title}' updated successfully.")
            return redirect('tasks:manager_task_list')

    return render(request, 'tasks/manager_task_form.html', {'form': form, 'title': 'Edit Task Details'})


@login_required
@task_authority_required
def manager_task_cancel(request, pk):
    task = get_object_or_404(Task, pk=pk, created_by=request.user)
    if task.is_cancelled:
        messages.error(request, "Task is already cancelled.")
        return redirect('tasks:manager_task_list')

    user_role = 'Admin' if request.user.role == 'ADMIN' else 'Manager'

    task.is_cancelled = True
    task.save()

    # Audit Log Cancellation
    TaskAuditLog.objects.create(
        username=request.user.username,
        user_role=user_role,
        task_name=task.title,
        action_performed='Task Cancellation',
        previous_value='Active',
        updated_value='Cancelled'
    )

    # Notify assignees
    for assignment in task.assignments.all():
        Notification.objects.create(
            recipient=assignment.employee,
            title="Task Cancelled",
            message=f"{user_role} {request.user.username} has cancelled the task: '{task.title}'."
        )

    messages.success(request, f"Task '{task.title}' has been successfully cancelled.")
    return redirect('tasks:manager_task_list')


@login_required
@task_authority_required
def manager_task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk, created_by=request.user)
    assignments = task.assignments.select_related('employee').all()
    comments = task.comments.select_related('author').order_by('created_at')
    attachments = task.attachments.select_related('uploaded_by').all()
    
    user_role = 'Admin' if request.user.role == 'ADMIN' else 'Manager'
    
    comment_form = TaskCommentForm(request.POST or None)
    if request.method == 'POST' and 'comment_submit' in request.POST:
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()

            # Audit Log Comment
            TaskAuditLog.objects.create(
                username=request.user.username,
                user_role=user_role,
                task_name=task.title,
                action_performed='Add Comment',
                previous_value=None,
                updated_value=comment.content[:50]
            )

            # Notify assignees
            for assignment in assignments:
                Notification.objects.create(
                    recipient=assignment.employee,
                    title="New Comment on Task",
                    message=f"{user_role} {request.user.username} commented on task: '{task.title}'."
                )
            return redirect('tasks:manager_task_detail', pk=task.pk)

    # Handle completion acceptance and rework requests
    if request.method == 'POST':
        action = request.POST.get('action')
        assignment_id = request.POST.get('assignment_id')
        
        if action and assignment_id:
            assignment = get_object_or_404(TaskAssignment, pk=assignment_id, task=task)
            
            if action == 'accept':
                old_status = assignment.status
                assignment.status = 'APPROVED'
                assignment.save()

                # Audit Log Acceptance
                TaskAuditLog.objects.create(
                    username=request.user.username,
                    user_role=user_role,
                    task_name=task.title,
                    action_performed='Completion Accepted',
                    previous_value=old_status,
                    updated_value='APPROVED'
                )

                # Notify employee
                Notification.objects.create(
                    recipient=assignment.employee,
                    title="Task Completion Accepted",
                    message=f"{user_role} {request.user.username} accepted task completion for '{task.title}'."
                )
                messages.success(request, f"Completion accepted for {assignment.employee.username}.")
                return redirect('tasks:manager_task_detail', pk=task.pk)
                
            elif action == 'rework':
                rework_comments = request.POST.get('rework_comments')
                if not rework_comments or not rework_comments.strip():
                    messages.error(request, "Rework comments/reason is mandatory.")
                    return redirect('tasks:manager_task_detail', pk=task.pk)

                old_status = assignment.status
                assignment.status = 'REWORK'
                assignment.save()

                # Save comment
                comment = TaskComment.objects.create(
                    task=task,
                    author=request.user,
                    content=f"[REWORK REQUESTED] {rework_comments}"
                )

                # Audit Log Rework
                TaskAuditLog.objects.create(
                    username=request.user.username,
                    user_role=user_role,
                    task_name=task.title,
                    action_performed='Rework Requested',
                    previous_value=old_status,
                    updated_value='REWORK'
                )

                # Notify employee
                Notification.objects.create(
                    recipient=assignment.employee,
                    title="Task Returned for Rework",
                    message=f"{user_role} {request.user.username} returned task '{task.title}' for rework: {rework_comments[:60]}..."
                )
                messages.warning(request, f"Rework requested for {assignment.employee.username}.")
                return redirect('tasks:manager_task_detail', pk=task.pk)

    context = {
        'task': task,
        'assignments': assignments,
        'comments': comments,
        'attachments': attachments,
        'comment_form': comment_form,
    }
    return render(request, 'tasks/manager_task_detail.html', context)


# --- EMPLOYEE VIEWS ---

@login_required
@regular_employee_required
def employee_task_list(request):
    today = date.today()
    assignments = TaskAssignment.objects.filter(employee=request.user, task__is_cancelled=False).select_related('task', 'task__created_by').order_by('-assigned_at')
    
    # Calculate Summary Statistics
    total_tasks = assignments.count()
    pending_tasks = assignments.filter(status__in=['NOT_STARTED', 'ON_HOLD', 'REWORK']).count()
    in_progress_tasks = assignments.filter(status='IN_PROGRESS').count()
    completed_tasks = assignments.filter(status='APPROVED').count()
    
    overdue_tasks = assignments.filter(
        task__due_date__lt=today
    ).exclude(status='APPROVED').count()

    context = {
        'assignments': assignments,
        'total_tasks': total_tasks,
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
    }
    return render(request, 'tasks/employee_task_list.html', context)


@login_required
@regular_employee_required
def employee_task_detail(request, pk):
    assignment = get_object_or_404(TaskAssignment, pk=pk, employee=request.user, task__is_cancelled=False)
    task = assignment.task
    comments = task.comments.select_related('author').order_by('created_at')
    attachments = task.attachments.select_related('uploaded_by').all()

    form = EmployeeTaskUpdateForm(request.POST or None, request.FILES or None, instance=assignment)
    comment_form = TaskCommentForm(request.POST or None)

    if request.method == 'POST':
        if 'comment_submit' in request.POST:
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.task = task
                comment.author = request.user
                comment.save()

                # Audit Log Comment
                TaskAuditLog.objects.create(
                    username=request.user.username,
                    user_role='Employee',
                    task_name=task.title,
                    action_performed='Add Comment',
                    previous_value=None,
                    updated_value=comment.content[:50]
                )

                # Notify Manager / Creator
                Notification.objects.create(
                    recipient=task.created_by,
                    title="New Comment from Employee",
                    message=f"Employee {request.user.username} commented on task: '{task.title}'."
                )
                return redirect('tasks:employee_task_detail', pk=assignment.pk)

        elif 'status_submit' in request.POST:
            if form.is_valid():
                old_status = assignment.status
                updated_assignment = form.save(commit=False)
                new_status = form.cleaned_data['status']
                
                if new_status == 'COMPLETED':
                    updated_assignment.status = 'COMPLETED'
                    updated_assignment.completion_submitted_at = timezone.now()
                    
                    # Notify Manager / Creator
                    Notification.objects.create(
                        recipient=task.created_by,
                        title="Task Marked as Completed",
                        message=f"Employee {request.user.username} has submitted task '{task.title}' for review."
                    )
                    action_str = 'Completion Requests'
                else:
                    action_str = 'Status Changes'
                
                updated_assignment.save()

                # Audit Log Status
                TaskAuditLog.objects.create(
                    username=request.user.username,
                    user_role='Employee',
                    task_name=task.title,
                    action_performed=action_str,
                    previous_value=old_status,
                    updated_value=new_status
                )

                # Optional comment
                comment_text = form.cleaned_data.get('comment')
                if comment_text and comment_text.strip():
                    TaskComment.objects.create(
                        task=task,
                        author=request.user,
                        content=comment_text
                    )
                    TaskAuditLog.objects.create(
                        username=request.user.username,
                        user_role='Employee',
                        task_name=task.title,
                        action_performed='Progress Update Comment',
                        previous_value=None,
                        updated_value=comment_text[:50]
                    )

                # Optional attachment
                uploaded_file = request.FILES.get('attachment')
                if uploaded_file:
                    TaskAttachment.objects.create(
                        task=task,
                        uploaded_by=request.user,
                        file=uploaded_file,
                        filename=uploaded_file.name
                    )
                    TaskAuditLog.objects.create(
                        username=request.user.username,
                        user_role='Employee',
                        task_name=task.title,
                        action_performed='File Upload',
                        previous_value=None,
                        updated_value=uploaded_file.name
                    )

                messages.success(request, "Task status updated successfully.")
                return redirect('tasks:employee_task_detail', pk=assignment.pk)

    context = {
        'assignment': assignment,
        'task': task,
        'comments': comments,
        'attachments': attachments,
        'form': form,
        'comment_form': comment_form,
    }
    return render(request, 'tasks/employee_task_detail.html', context)


# --- EXPORT REPORT VIEWS ---

@login_required
@task_authority_required
def export_tasks_excel(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="team_task_performance_{timezone.localdate()}.csv"'
    
    writer = csv.writer(response)
    user_role = 'Admin' if request.user.role == 'ADMIN' else 'Manager'
    
    writer.writerow(['Team Task Performance & Productivity Report'])
    writer.writerow([f'Generated By: {request.user.get_full_name() or request.user.username} ({user_role})'])
    writer.writerow([f'Date: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([])
    
    # Resolve enable_employee_types
    enable_employee_types = True
    if request.user.role == 'ADMIN':
        admin_user = request.user
    else:
        admin_user = request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None
        
    if admin_user:
        try:
            enable_employee_types = admin_user.organization.enable_employee_types
        except Exception:
            pass

    if not enable_employee_types:
        reporting_employees = User.objects.filter(
            role='EMPLOYEE',
            employeeprofile__created_by=admin_user,
            employeeprofile__status='ACTIVE'
        )
    else:
        reporting_employees = User.objects.filter(
            role='EMPLOYEE',
            employeeprofile__reporting_manager=request.user,
            employeeprofile__status='ACTIVE'
        )
    
    writer.writerow(['Employee Name', 'Username', 'Total Tasks Assigned', 'Completion Accepted', 'Pending Tasks', 'Overdue Tasks', 'Completion Rate'])
    
    today = date.today()
    for emp in reporting_employees:
        emp_assignments = TaskAssignment.objects.filter(employee=emp, task__is_cancelled=False)
        total = emp_assignments.count()
        done = emp_assignments.filter(status='APPROVED').count()
        pending = emp_assignments.filter(status__in=['NOT_STARTED', 'IN_PROGRESS', 'ON_HOLD', 'REWORK']).count()
        overdue = emp_assignments.filter(task__due_date__lt=today).exclude(status='APPROVED').count()
        rate = f"{int((done / total) * 100)}%" if total > 0 else "0%"
        
        writer.writerow([
            emp.get_full_name() or emp.username,
            emp.username,
            total,
            done,
            pending,
            overdue,
            rate
        ])
        
    writer.writerow([])
    writer.writerow(['Detailed Tasks Assignment List'])
    writer.writerow(['Task Title', 'Assigned To', 'Priority', 'Start Date', 'Due Date', 'Status', 'Days Overdue/Remaining'])
    
    assignments = TaskAssignment.objects.filter(
        task__created_by=request.user,
        task__is_cancelled=False
    ).select_related('task', 'employee').order_by('task__due_date')
    
    for a in assignments:
        diff_days = (a.task.due_date - today).days
        if a.status == 'APPROVED':
            status_desc = 'Completed (Approved)'
            days_str = 'N/A'
        elif diff_days < 0:
            status_desc = a.get_status_display()
            days_str = f"{abs(diff_days)} days overdue"
        else:
            status_desc = a.get_status_display()
            days_str = f"{diff_days} days remaining"
            
        writer.writerow([
            a.task.title,
            a.employee.username,
            a.task.get_priority_display(),
            a.task.start_date,
            a.task.due_date,
            status_desc,
            days_str
        ])
        
    return response


@login_required
@task_authority_required
def export_tasks_pdf(request):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=20
    )
    
    section_style = ParagraphStyle(
        'DocSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=15,
        spaceAfter=10
    )
    
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#334155')
    )

    cell_bold_style = ParagraphStyle(
        'CellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    
    cell_header_style = ParagraphStyle(
        'CellHeader',
        parent=cell_style,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )

    elements = []
    
    user_role = 'Admin' if request.user.role == 'ADMIN' else 'Manager'
    elements.append(Paragraph(f"{user_role} Team Task Productivity Report", title_style))
    manager_name = request.user.get_full_name() or request.user.username
    elements.append(Paragraph(f"Generated By: {manager_name} | Date: {timezone.now().strftime('%Y-%m-%d %I:%M %p')}", subtitle_style))
    elements.append(Spacer(1, 10))
    
    elements.append(Paragraph("1. Team Performance & Completion Summaries", section_style))
    
    headers = [
        Paragraph("Employee Name", cell_header_style),
        Paragraph("Assigned", cell_header_style),
        Paragraph("Approved", cell_header_style),
        Paragraph("Pending", cell_header_style),
        Paragraph("Overdue", cell_header_style),
        Paragraph("Completion %", cell_header_style),
    ]
    
    table_data = [headers]
    
    # Resolve enable_employee_types
    enable_employee_types = True
    if request.user.role == 'ADMIN':
        admin_user = request.user
    else:
        admin_user = request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None
        
    if admin_user:
        try:
            enable_employee_types = admin_user.organization.enable_employee_types
        except Exception:
            pass

    if not enable_employee_types:
        reporting_employees = User.objects.filter(
            role='EMPLOYEE',
            employeeprofile__created_by=admin_user,
            employeeprofile__status='ACTIVE'
        )
    else:
        reporting_employees = User.objects.filter(
            role='EMPLOYEE',
            employeeprofile__reporting_manager=request.user,
            employeeprofile__status='ACTIVE'
        )
    
    today = date.today()
    for emp in reporting_employees:
        emp_assignments = TaskAssignment.objects.filter(employee=emp, task__is_cancelled=False)
        total = emp_assignments.count()
        done = emp_assignments.filter(status='APPROVED').count()
        pending = emp_assignments.filter(status__in=['NOT_STARTED', 'IN_PROGRESS', 'ON_HOLD', 'REWORK']).count()
        overdue = emp_assignments.filter(task__due_date__lt=today).exclude(status='APPROVED').count()
        rate = f"{int((done / total) * 100)}%" if total > 0 else "0%"
        
        row = [
            Paragraph(emp.get_full_name() or emp.username, cell_style),
            Paragraph(str(total), cell_style),
            Paragraph(str(done), cell_style),
            Paragraph(str(pending), cell_style),
            Paragraph(str(overdue), cell_style),
            Paragraph(rate, cell_bold_style),
        ]
        table_data.append(row)
        
    t1 = Table(table_data, colWidths=[180, 70, 70, 70, 70, 80])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3b82f6')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8fafc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f1f5f9')]),
        ('TOPPADDING', (0,1), (-1,-1), 5),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
    ]))
    
    elements.append(t1)
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("2. Complete Tasks and Overdue Assignments Tracker", section_style))
    
    headers2 = [
        Paragraph("Task Name", cell_header_style),
        Paragraph("Assignee", cell_header_style),
        Paragraph("Priority", cell_header_style),
        Paragraph("Due Date", cell_header_style),
        Paragraph("Status", cell_header_style),
        Paragraph("Days Overdue/Remaining", cell_header_style),
    ]
    
    table_data2 = [headers2]
    
    assignments = TaskAssignment.objects.filter(
        task__created_by=request.user,
        task__is_cancelled=False
    ).select_related('task', 'employee').order_by('task__due_date')
    
    for a in assignments:
        diff_days = (a.task.due_date - today).days
        if a.status == 'APPROVED':
            status_desc = 'Approved'
            days_str = 'N/A'
        elif diff_days < 0:
            status_desc = a.get_status_display()
            days_str = f"{abs(diff_days)} d overdue"
        else:
            status_desc = a.get_status_display()
            days_str = f"{diff_days} d remaining"
            
        row = [
            Paragraph(a.task.title, cell_style),
            Paragraph(a.employee.username, cell_style),
            Paragraph(a.task.get_priority_display(), cell_style),
            Paragraph(str(a.task.due_date), cell_style),
            Paragraph(status_desc, cell_bold_style if a.status == 'APPROVED' or diff_days < 0 else cell_style),
            Paragraph(days_str, cell_bold_style if diff_days < 0 else cell_style),
        ]
        table_data2.append(row)
        
    t2 = Table(table_data2, colWidths=[150, 80, 60, 75, 75, 100])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8fafc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f1f5f9')]),
        ('TOPPADDING', (0,1), (-1,-1), 5),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
    ]))
    
    elements.append(t2)
    
    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="task_performance_report_{timezone.localdate()}.pdf"'
    response.write(pdf)
    return response
