from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.accounts.permissions import super_admin_required, admin_required, employee_required
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
@admin_required
def admin_dashboard(request):
    """
    Renders analytics summary for Company Administrators. Isolated by creator.
    """
    today = timezone.localdate()
    
    total_employees = EmployeeProfile.objects.filter(status='ACTIVE', created_by=request.user).count()
    checked_in_today = AttendanceRecord.objects.filter(date=today, user__employeeprofile__created_by=request.user).count()
    late_today = AttendanceRecord.objects.filter(date=today, status='LATE', user__employeeprofile__created_by=request.user).count()
    pending_leaves = LeaveRequest.objects.filter(status='PENDING', user__employeeprofile__created_by=request.user).count()
    enrolled_faces = FaceEnrollment.objects.filter(user__employeeprofile__created_by=request.user).count()
    
    # Recent attendance logs
    recent_records = AttendanceRecord.objects.filter(date=today, user__employeeprofile__created_by=request.user).select_related('user')[:5]
    
    context = {
        'total_employees': total_employees,
        'checked_in_today': checked_in_today,
        'late_today': late_today,
        'pending_leaves': pending_leaves,
        'enrolled_faces': enrolled_faces,
        'recent_records': recent_records,
    }
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
    
    # Month aggregates
    start_of_month = today.replace(day=1)
    present_days = AttendanceRecord.objects.filter(user=request.user, date__gte=start_of_month, status__in=['PRESENT', 'LATE']).count()
    late_days = AttendanceRecord.objects.filter(user=request.user, date__gte=start_of_month, status='LATE').count()
    leaves_taken = LeaveRequest.objects.filter(user=request.user, status='APPROVED').count()
    
    try:
        profile = request.user.employeeprofile
    except Exception:
        profile = None

    context = {
        'checked_in': checked_in,
        'checked_out': checked_out,
        'check_in_time': record.check_in if checked_in else None,
        'check_out_time': record.check_out if checked_out else None,
        'present_days': present_days,
        'late_days': late_days,
        'leaves_taken': leaves_taken,
        'record': record,
        'profile': profile,
        'profile_form': profile_form,
    }
    return render(request, 'dashboards/employee_dashboard.html', context)
