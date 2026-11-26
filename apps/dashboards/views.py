from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.accounts.permissions import super_admin_required, admin_required, employee_required, admin_or_hr_or_manager_required
from apps.departments.models import Department
from apps.employee_management.models import EmployeeProfile
from apps.biometric.models import FaceEnrollment
from apps.attendance.models import AttendanceRecord, AttendanceLog
from apps.leave_management.models import LeaveRequest
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def dispatcher(request):
    """
    Dispatches users to their corresponding dashboard based on security roles.
    """
    if request.user.role == 'SUPER_ADMIN':
        return redirect('dashboards:super_admin_dashboard')
    elif request.user.role == 'ADMIN':
        return redirect('dashboards:admin_dashboard')
    elif request.user.role == 'EMPLOYEE':
        if request.user.is_hr or request.user.is_manager:
            return redirect('dashboards:admin_dashboard')
        return redirect('dashboards:employee_dashboard')
    else:
        # Fallback to profile
        return redirect('accounts:profile')

@login_required
@super_admin_required
def super_admin_dashboard(request):
    """
    Renders analytics summary for the Super Administrator. Excludes employee details.
    """
    total_admins = User.objects.filter(role='ADMIN').count()
    total_depts = Department.objects.count()
    
    context = {
        'total_admins': total_admins,
        'total_departments': total_depts,
    }
    return render(request, 'dashboards/super_admin_dashboard.html', context)

@login_required
@admin_or_hr_or_manager_required
def admin_dashboard(request):
    """
    Renders analytics summary for Company Administrators. Isolated by creator.
    """
    today = timezone.localdate()
    
    if request.user.role == 'ADMIN':
        admin_user = request.user
    else:
        admin_user = request.user.employeeprofile.created_by
        
    enable_employee_types = True
    if admin_user:
        try:
            enable_employee_types = admin_user.organization.enable_employee_types
        except Exception:
            pass
        
    if enable_employee_types and request.user.role == 'EMPLOYEE' and request.user.employeeprofile.employee_type == 'MANAGER':
        total_employees = EmployeeProfile.objects.filter(status='ACTIVE', reporting_manager=request.user).count()
        checked_in_today = AttendanceRecord.objects.filter(date=today, user__employeeprofile__reporting_manager=request.user).count()
        late_today = AttendanceRecord.objects.filter(date=today, status='LATE', user__employeeprofile__reporting_manager=request.user).count()
        pending_leaves = LeaveRequest.objects.filter(status='PENDING', user__employeeprofile__reporting_manager=request.user).count()
        enrolled_faces = FaceEnrollment.objects.filter(user__employeeprofile__reporting_manager=request.user).count()
        recent_records = AttendanceRecord.objects.filter(date=today, user__employeeprofile__reporting_manager=request.user).select_related('user')[:5]
    else:
        total_employees = EmployeeProfile.objects.filter(status='ACTIVE', created_by=admin_user).count()
        checked_in_today = AttendanceRecord.objects.filter(date=today, user__employeeprofile__created_by=admin_user).count()
        late_today = AttendanceRecord.objects.filter(date=today, status='LATE', user__employeeprofile__created_by=admin_user).count()
        pending_leaves = LeaveRequest.objects.filter(status='PENDING', user__employeeprofile__created_by=admin_user).count()
        enrolled_faces = FaceEnrollment.objects.filter(user__employeeprofile__created_by=admin_user).count()
        recent_records = AttendanceRecord.objects.filter(date=today, user__employeeprofile__created_by=admin_user).select_related('user')[:5]
        
    task_stats = {}
    if enable_employee_types and request.user.role == 'EMPLOYEE' and request.user.employeeprofile.employee_type == 'MANAGER':
        from apps.tasks.models import Task, TaskAssignment
        task_stats = {
            'task_total': Task.objects.filter(created_by=request.user).count(),
            'task_completed': TaskAssignment.objects.filter(task__created_by=request.user, status='APPROVED').count(),
            'task_pending': TaskAssignment.objects.filter(task__created_by=request.user, status__in=['NOT_STARTED', 'ON_HOLD', 'REWORK'], task__is_cancelled=False).count(),
            'task_in_progress': TaskAssignment.objects.filter(task__created_by=request.user, status='IN_PROGRESS', task__is_cancelled=False).count(),
            'task_overdue': TaskAssignment.objects.filter(task__created_by=request.user, task__due_date__lt=today, task__is_cancelled=False).exclude(status='APPROVED').count(),
            'is_manager': True,
            'show_tasks_overview': True
        }
    elif not enable_employee_types and request.user.role == 'ADMIN':
        from apps.tasks.models import Task, TaskAssignment
        task_stats = {
            'task_total': Task.objects.filter(created_by=request.user).count(),
            'task_completed': TaskAssignment.objects.filter(task__created_by=request.user, status='APPROVED').count(),
            'task_pending': TaskAssignment.objects.filter(task__created_by=request.user, status__in=['NOT_STARTED', 'ON_HOLD', 'REWORK'], task__is_cancelled=False).count(),
            'task_in_progress': TaskAssignment.objects.filter(task__created_by=request.user, status='IN_PROGRESS', task__is_cancelled=False).count(),
            'task_overdue': TaskAssignment.objects.filter(task__created_by=request.user, task__due_date__lt=today, task__is_cancelled=False).exclude(status='APPROVED').count(),
            'show_tasks_overview': True
        }
        
    context = {
        'total_employees': total_employees,
        'checked_in_today': checked_in_today,
        'late_today': late_today,
        'pending_leaves': pending_leaves,
        'enrolled_faces': enrolled_faces,
        'recent_records': recent_records,
    }
    context.update(task_stats)
    return render(request, 'dashboards/admin_dashboard.html', context)

@login_required
@employee_required
def employee_dashboard(request):
    """
    Renders user portal for Employees.
    """
    from apps.accounts.forms import UserProfileForm
    from django.contrib import messages
    
    today = timezone.localdate()
    now = timezone.now()
    
    # Load profile form
    user_profile_instance = request.user.userprofile
    profile_form = UserProfileForm(request.POST or None, request.FILES or None, instance=user_profile_instance, user=request.user)
    
    if request.method == 'POST':
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('dashboards:employee_dashboard')
        else:
            messages.error(request, "Please correct the errors in the profile form.")
            
    # Attendance state
    record = AttendanceRecord.objects.filter(user=request.user, date=today).first()
    checked_in = record is not None
    checked_out = record.check_out is not None if checked_in else False
    
    # Overtime state
    from apps.attendance.models import OvertimeRecord
    has_active_ot = False
    ot_completed_today = False
    if request.user.is_ot_enabled:
        active_ot = OvertimeRecord.objects.filter(user=request.user, date=today, check_out__isnull=True).first()
        if active_ot:
            has_active_ot = True
        completed_ot = OvertimeRecord.objects.filter(user=request.user, date=today, check_out__isnull=False).first()
        if completed_ot:
            ot_completed_today = True

    # Month aggregates
    start_of_month = today.replace(day=1)
    present_days = AttendanceRecord.objects.filter(user=request.user, date__gte=start_of_month, status__in=['PRESENT', 'LATE']).count()
    late_days = AttendanceRecord.objects.filter(user=request.user, date__gte=start_of_month, status='LATE').count()
    leaves_taken = LeaveRequest.objects.filter(user=request.user, status='APPROVED').count()
    
    try:
        profile = request.user.employeeprofile
    except Exception:
        profile = None

    # Employee Task metrics
    from apps.tasks.models import TaskAssignment
    task_total = TaskAssignment.objects.filter(employee=request.user, task__is_cancelled=False).count()
    task_completed = TaskAssignment.objects.filter(employee=request.user, task__is_cancelled=False, status='APPROVED').count()
    task_pending = TaskAssignment.objects.filter(employee=request.user, task__is_cancelled=False, status__in=['NOT_STARTED', 'ON_HOLD', 'REWORK']).count()
    task_in_progress = TaskAssignment.objects.filter(employee=request.user, task__is_cancelled=False, status='IN_PROGRESS').count()
    task_overdue = TaskAssignment.objects.filter(employee=request.user, task__is_cancelled=False, task__due_date__lt=today).exclude(status='APPROVED').count()

    context = {
        'checked_in': checked_in,
        'checked_out': checked_out,
        'has_active_ot': has_active_ot,
        'ot_completed_today': ot_completed_today,
        'check_in_time': record.check_in if checked_in else None,
        'check_out_time': record.check_out if checked_out else None,
        'present_days': present_days,
        'late_days': late_days,
        'leaves_taken': leaves_taken,
        'record': record,
        'profile': profile,
        'profile_form': profile_form,
        'task_total': task_total,
        'task_completed': task_completed,
        'task_pending': task_pending,
        'task_in_progress': task_in_progress,
        'task_overdue': task_overdue,
    }
    return render(request, 'dashboards/employee_dashboard.html', context)
