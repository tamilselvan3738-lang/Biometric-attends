from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import LeaveRequest
from .forms import LeaveRequestForm
from apps.accounts.permissions import admin_required, employee_required, admin_or_super_admin_required
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
            
            # Send Notification to Admins (Simple placeholder logic)
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
@admin_required
def leave_requests(request):
    """
    Lists all PENDING leave requests for administrative review. Isolated by creator.
    """
    leaves = LeaveRequest.objects.filter(status='PENDING', user__employeeprofile__created_by=request.user).select_related('user')
    approved = LeaveRequest.objects.filter(status='APPROVED', user__employeeprofile__created_by=request.user).select_related('user')
    rejected = LeaveRequest.objects.filter(status='REJECTED', user__employeeprofile__created_by=request.user).select_related('user')
    context = {
        'pending_leaves': leaves,
        'approved_leaves': approved,
        'rejected_leaves': rejected
    }
    return render(request, 'leave_management/leave_requests.html', context)

@login_required
@admin_required
def approve_leave(request, pk):
    """
    Action endpoint to approve a leave request.
    """
    leave = get_object_or_404(LeaveRequest, pk=pk, user__employeeprofile__created_by=request.user)
    if request.method == 'POST':
        leave.status = 'APPROVED'
        leave.approved_by = request.user
        leave.save()
        
        # Create user notification
        Notification.objects.create(
            recipient=leave.user,
            title="Leave Approved",
            message=f"Your leave request for {leave.leave_type} ({leave.start_date} to {leave.end_date}) has been approved.",
            is_read=False
        )
        messages.success(request, f"Leave request for {leave.user.username} approved.")
    return redirect('leave_management:leave_requests')

@login_required
@admin_required
def reject_leave(request, pk):
    """
    Action endpoint to reject a leave request.
    """
    leave = get_object_or_404(LeaveRequest, pk=pk, user__employeeprofile__created_by=request.user)
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', 'No reason specified.')
        leave.status = 'REJECTED'
        leave.approved_by = request.user
        leave.rejection_reason = rejection_reason
        leave.save()
        
        Notification.objects.create(
            recipient=leave.user,
            title="Leave Rejected",
            message=f"Your leave request for {leave.leave_type} has been rejected. Reason: {rejection_reason}",
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
        
    if request.user.role == 'ADMIN':
        leave = get_object_or_404(LeaveRequest.objects.select_related('user', 'approved_by'), pk=pk, user__employeeprofile__created_by=request.user)
    else: # EMPLOYEE
        leave = get_object_or_404(LeaveRequest.objects.select_related('user', 'approved_by'), pk=pk, user=request.user)
        
    return render(request, 'leave_management/leave_details.html', {'leave': leave})
