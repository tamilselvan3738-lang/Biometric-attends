from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import LeaveRequest
from .forms import LeaveRequestForm
from apps.accounts.permissions import admin_required, employee_required, admin_or_super_admin_required, admin_or_manager_required, admin_or_hr_or_manager_required
from apps.notifications.models import Notification

@login_required
@employee_required
def apply_leave(request):
    """
    Form for employees to apply for leave.
    """
    form = LeaveRequestForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            leave = form.save(commit=False)
            leave.user = request.user
            leave.status = 'PENDING'
            leave.save()
            
            # Send Notification to Approver according to approval matrix
            try:
                profile = request.user.employeeprofile
                admin_user = profile.created_by
                enable_employee_types = True
                if admin_user:
                    try:
                        enable_employee_types = admin_user.organization.enable_employee_types
                    except Exception:
                        pass
                        
                approver = None
                if not enable_employee_types:
                    approver = admin_user
                elif profile.employee_type == 'EMPLOYEE':
                    approver = profile.reporting_manager
                    # Safe fallback in case reporting manager is unassigned
                    if not approver:
                        approver = admin_user
                else:
                    approver = admin_user
                
                if approver:
                    Notification.objects.create(
                        recipient=approver,
                        title="New Leave Request",
                        message=f"Leave request submitted by {request.user.get_full_name() or request.user.username} from {leave.start_date} to {leave.end_date}. Reason: {leave.reason}",
                        is_read=False
                    )
            except Exception:
                pass

            messages.success(request, "Your leave application has been submitted successfully.")
            return redirect('leave_management:leave_history')
        else:
            messages.error(request, "Failed to submit leave request. Resolve form errors.")
            
    return render(request, 'leave_management/apply_leave.html', {'form': form})

@login_required
@employee_required
def leave_history(request):
    """
    Lists applied leaves for the logged-in employee.
    """
    leaves = LeaveRequest.objects.filter(user=request.user)
    return render(request, 'leave_management/leave_history.html', {'leaves': leaves})

@login_required
@admin_or_manager_required
def leave_requests(request):
    """
    Lists all leave requests for administrative review.
    """
    # Resolve creator Admin
    admin_user = request.user if request.user.role == 'ADMIN' else (request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None)
    
    enable_employee_types = True
    if admin_user:
        try:
            enable_employee_types = admin_user.organization.enable_employee_types
        except Exception:
            pass

    if not enable_employee_types and request.user.role != 'ADMIN':
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Employee Type functionality is disabled.")

    if request.user.role == 'ADMIN':
        if not enable_employee_types:
            leaves = LeaveRequest.objects.filter(
                status='PENDING', 
                user__employeeprofile__created_by=request.user
            ).select_related('user')
            approved = LeaveRequest.objects.filter(
                status='APPROVED', 
                user__employeeprofile__created_by=request.user
            ).select_related('user')
            rejected = LeaveRequest.objects.filter(
                status='REJECTED', 
                user__employeeprofile__created_by=request.user
            ).select_related('user')
        else:
            leaves = LeaveRequest.objects.filter(
                status='PENDING', 
                user__employeeprofile__created_by=request.user,
                user__employeeprofile__employee_type__in=['HR_TEAM', 'MANAGER']
            ).select_related('user')
            approved = LeaveRequest.objects.filter(
                status='APPROVED', 
                user__employeeprofile__created_by=request.user,
                user__employeeprofile__employee_type__in=['HR_TEAM', 'MANAGER']
            ).select_related('user')
            rejected = LeaveRequest.objects.filter(
                status='REJECTED', 
                user__employeeprofile__created_by=request.user,
                user__employeeprofile__employee_type__in=['HR_TEAM', 'MANAGER']
            ).select_related('user')
    elif request.user.role == 'EMPLOYEE' and request.user.employeeprofile.employee_type == 'MANAGER':
        leaves = LeaveRequest.objects.filter(
            status='PENDING', 
            user__employeeprofile__reporting_manager=request.user,
            user__employeeprofile__employee_type='EMPLOYEE'
        ).select_related('user')
        approved = LeaveRequest.objects.filter(
            status='APPROVED', 
            user__employeeprofile__reporting_manager=request.user,
            user__employeeprofile__employee_type='EMPLOYEE'
        ).select_related('user')
        rejected = LeaveRequest.objects.filter(
            status='REJECTED', 
            user__employeeprofile__reporting_manager=request.user,
            user__employeeprofile__employee_type='EMPLOYEE'
        ).select_related('user')
    else:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to view leave requests.")
        
    context = {
        'pending_leaves': leaves,
        'approved_leaves': approved,
        'rejected_leaves': rejected
    }
    return render(request, 'leave_management/leave_requests.html', context)

@login_required
@admin_or_manager_required
def approve_leave(request, pk):
    """
    Action endpoint to approve a leave request.
    """
    leave = get_object_or_404(LeaveRequest, pk=pk)
    
    # Resolve creator Admin
    admin_user = request.user if request.user.role == 'ADMIN' else (request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None)
    enable_employee_types = True
    if admin_user:
        try:
            enable_employee_types = admin_user.organization.enable_employee_types
        except Exception:
            pass

    from django.core.exceptions import PermissionDenied
    is_allowed = False
    try:
        emp_profile = leave.user.employeeprofile
        if request.user.role == 'ADMIN' and emp_profile.created_by == request.user:
            if not enable_employee_types or emp_profile.employee_type in ['HR_TEAM', 'MANAGER']:
                is_allowed = True
        elif request.user.role == 'EMPLOYEE' and request.user.is_manager and emp_profile.reporting_manager == request.user:
            if enable_employee_types and emp_profile.employee_type == 'EMPLOYEE':
                is_allowed = True
    except Exception:
        pass
        
    if not is_allowed:
        raise PermissionDenied("You do not have permission to approve this leave request.")
        
    if request.method == 'POST':
        prev_status = leave.status
        remarks = request.POST.get('remarks', 'Approved.')
        leave.status = 'APPROVED'
        leave.approved_by = request.user
        leave.remarks = remarks
        leave.save()
        
        # Log approval audit
        from .models import LeaveApprovalAuditLog
        LeaveApprovalAuditLog.objects.create(
            leave_request=leave,
            action='APPROVED',
            action_by=request.user,
            previous_status=prev_status,
            updated_status='APPROVED',
            remarks=remarks
        )
        
        # Create user notification
        Notification.objects.create(
            recipient=leave.user,
            title="Leave Approved",
            message=f"Your leave request for {leave.get_leave_type_display()} ({leave.start_date} to {leave.end_date}) has been approved. Comments: {remarks}",
            is_read=False
        )
        messages.success(request, f"Leave request for {leave.user.username} approved.")
    return redirect('leave_management:leave_requests')

@login_required
@admin_or_manager_required
def reject_leave(request, pk):
    """
    Action endpoint to reject a leave request.
    """
    leave = get_object_or_404(LeaveRequest, pk=pk)
    
    # Resolve creator Admin
    admin_user = request.user if request.user.role == 'ADMIN' else (request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None)
    enable_employee_types = True
    if admin_user:
        try:
            enable_employee_types = admin_user.organization.enable_employee_types
        except Exception:
            pass

    from django.core.exceptions import PermissionDenied
    is_allowed = False
    try:
        emp_profile = leave.user.employeeprofile
        if request.user.role == 'ADMIN' and emp_profile.created_by == request.user:
            if not enable_employee_types or emp_profile.employee_type in ['HR_TEAM', 'MANAGER']:
                is_allowed = True
        elif request.user.role == 'EMPLOYEE' and request.user.is_manager and emp_profile.reporting_manager == request.user:
            if enable_employee_types and emp_profile.employee_type == 'EMPLOYEE':
                is_allowed = True
    except Exception:
        pass
        
    if not is_allowed:
        raise PermissionDenied("You do not have permission to reject this leave request.")
        
    if request.method == 'POST':
        prev_status = leave.status
        rejection_reason = request.POST.get('rejection_reason', 'No reason specified.')
        remarks = rejection_reason
        leave.status = 'REJECTED'
        leave.approved_by = request.user
        leave.rejection_reason = rejection_reason
        leave.remarks = remarks
        leave.save()
        
        # Log rejection audit
        from .models import LeaveApprovalAuditLog
        LeaveApprovalAuditLog.objects.create(
            leave_request=leave,
            action='REJECTED',
            action_by=request.user,
            previous_status=prev_status,
            updated_status='REJECTED',
            rejection_reason=rejection_reason,
            remarks=remarks
        )
        
        Notification.objects.create(
            recipient=leave.user,
            title="Leave Rejected",
            message=f"Your leave request for {leave.get_leave_type_display()} has been rejected. Reason: {rejection_reason}",
            is_read=False
        )
        messages.success(request, f"Leave request for {leave.user.username} rejected.")
    return redirect('leave_management:leave_requests')

@login_required
def leave_details(request, pk):
    """
    View details of a specific leave request.
    """
    if request.user.role == 'SUPER_ADMIN':
        messages.error(request, "Access Denied: Super Admin cannot view leave details.")
        return redirect('dashboards:dispatcher')
        
    leave = get_object_or_404(LeaveRequest.objects.select_related('user', 'approved_by'), pk=pk)
    
    # Resolve creator Admin
    admin_user = request.user if request.user.role == 'ADMIN' else (request.user.employeeprofile.created_by if hasattr(request.user, 'employeeprofile') else None)
    enable_employee_types = True
    if admin_user:
        try:
            enable_employee_types = admin_user.organization.enable_employee_types
        except Exception:
            pass

    is_allowed = False
    if request.user.role == 'ADMIN':
        try:
            emp_profile = leave.user.employeeprofile
            if emp_profile.created_by == request.user:
                if not enable_employee_types or emp_profile.employee_type in ['HR_TEAM', 'MANAGER']:
                    is_allowed = True
        except Exception:
            pass
    elif leave.user == request.user:
        # Any employee can view their own leave
        is_allowed = True
    elif request.user.role == 'EMPLOYEE':
        try:
            profile_type = request.user.employeeprofile.employee_type
            # Manager can view leaves of Employees reporting to them
            if enable_employee_types and profile_type == 'MANAGER' and leave.user.employeeprofile.reporting_manager == request.user:
                if leave.user.employeeprofile.employee_type == 'EMPLOYEE':
                    is_allowed = True
        except Exception:
            pass
            
    if not is_allowed:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to view this leave request.")
        
    return render(request, 'leave_management/leave_details.html', {'leave': leave})
