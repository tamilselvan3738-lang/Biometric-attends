from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import CompanyProfile, SystemSetting
from .forms import AdminAddForm, AdminEditForm, CompanyProfileForm, SystemSettingForm
from apps.accounts.permissions import super_admin_required, admin_required

User = get_user_model()

@login_required
@super_admin_required
def admin_list(request):
    admins = User.objects.filter(role='ADMIN').select_related('limit', 'organization')
    return render(request, 'super_admin/admin_list.html', {'admins': admins})

@login_required
@super_admin_required
def create_admin(request):
    form = AdminAddForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Admin account successfully created.")
            return redirect('super_admin:admin_list')
        else:
            messages.error(request, "Failed to create Admin. Please fix form errors.")
    return render(request, 'super_admin/create_admin.html', {'form': form})

@login_required
@super_admin_required
def edit_admin(request, pk):
    admin_user = get_object_or_404(User, pk=pk, role='ADMIN')
    form = AdminEditForm(request.POST or None, request.FILES or None, instance=admin_user)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Admin account details updated.")
            return redirect('super_admin:admin_list')
        else:
            messages.error(request, "Failed to update Admin account.")
    return render(request, 'super_admin/edit_admin.html', {'form': form, 'admin_user': admin_user})

@login_required
@super_admin_required
def delete_admin(request, pk):
    admin_user = get_object_or_404(User, pk=pk, role='ADMIN')
    if request.method == 'POST':
        import os
        from apps.super_admin.models import TerminatedAccount
        from apps.notifications.models import Notification
        from apps.leave_management.models import LeaveRequest
        from apps.attendance.models import AttendanceRecord, OvertimeRecord, AttendanceLog
        from apps.biometric.models import FaceEnrollment, BiometricLog
        from apps.accounts.models import ForgotPasswordOTP
        from apps.super_admin.models import LimitRequest
        
        username = admin_user.username
        
        # 1. Purge all employees created by this admin
        employees = User.objects.filter(employeeprofile__created_by=admin_user)
        for emp in employees:
            Notification.objects.filter(recipient=emp).delete()
            LeaveRequest.objects.filter(user=emp).delete()
            AttendanceRecord.objects.filter(user=emp).delete()
            OvertimeRecord.objects.filter(user=emp).delete()
            AttendanceLog.objects.filter(user=emp).delete()
            
            # Biometrics
            enrollments = FaceEnrollment.objects.filter(user=emp)
            for enrollment in enrollments:
                try:
                    if enrollment.enrolled_image and os.path.exists(enrollment.enrolled_image.path):
                        os.remove(enrollment.enrolled_image.path)
                except Exception:
                    pass
            enrollments.delete()
            BiometricLog.objects.filter(user=emp).delete()
            
            ForgotPasswordOTP.objects.filter(user=emp).delete()
            
            # Profile files
            if hasattr(emp, 'employeeprofile'):
                ep = emp.employeeprofile
                try:
                    if ep.profile_image and os.path.exists(ep.profile_image.path):
                        os.remove(ep.profile_image.path)
                    if ep.document and os.path.exists(ep.document.path):
                        os.remove(ep.document.path)
                except Exception:
                    pass
                ep.delete()
            
            if hasattr(emp, 'userprofile'):
                up = emp.userprofile
                try:
                    if up.avatar and os.path.exists(up.avatar.path):
                        os.remove(up.avatar.path)
                except Exception:
                    pass
                up.delete()
                
            TerminatedAccount.objects.filter(username=emp.username).delete()
            emp.delete()
            
        # 2. Delete Admin's own data
        Notification.objects.filter(recipient=admin_user).delete()
        ForgotPasswordOTP.objects.filter(user=admin_user).delete()
        LimitRequest.objects.filter(admin=admin_user).delete()
        
        if hasattr(admin_user, 'limit'):
            admin_user.limit.delete()
            
        if hasattr(admin_user, 'organization'):
            org = admin_user.organization
            try:
                if org.logo and os.path.exists(org.logo.path):
                    os.remove(org.logo.path)
            except Exception:
                pass
            org.delete()
            
        if hasattr(admin_user, 'userprofile'):
            u_prof = admin_user.userprofile
            try:
                if u_prof.avatar and os.path.exists(u_prof.avatar.path):
                    os.remove(u_prof.avatar.path)
            except Exception:
                pass
            u_prof.delete()
            
        # Remove from TerminatedAccount
        TerminatedAccount.objects.filter(username=username).delete()
        
        # Finally delete Admin user itself
        admin_user.delete()
        
        messages.success(request, f"Admin account '{username}' and all associated employees/data have been permanently deleted.")
    return redirect('super_admin:admin_list')

@login_required
@super_admin_required
def deactivate_admin(request, pk):
    admin_user = get_object_or_404(User, pk=pk, role='ADMIN')
    if request.method == 'POST':
        from django.utils import timezone
        from apps.super_admin.models import TerminatedAccount
        
        admin_user.is_active = False
        admin_user.is_terminated = True
        admin_user.terminated_at = timezone.now()
        admin_user.terminated_by = request.user
        admin_user.save()
        
        # Deactivate all employee accounts created by this admin
        employees_to_deactivate = User.objects.filter(employeeprofile__created_by=admin_user)
        for emp in employees_to_deactivate:
            emp.is_active = False
            emp.is_terminated = True
            emp.terminated_at = timezone.now()
            emp.terminated_by = request.user
            emp.save()
            if hasattr(emp, 'employeeprofile'):
                emp.employeeprofile.status = 'INACTIVE'
                emp.employeeprofile.save()
            TerminatedAccount.objects.get_or_create(
                username=emp.username,
                defaults={'role': 'EMPLOYEE'}
            )
            
        TerminatedAccount.objects.get_or_create(
            username=admin_user.username,
            defaults={'role': 'ADMIN'}
        )
        
        messages.success(request, f"Admin account '{admin_user.username}' and all associated employee accounts have been deactivated.")
    return redirect('super_admin:admin_list')

@login_required
@super_admin_required
def activate_admin(request, pk):
    admin_user = get_object_or_404(User, pk=pk, role='ADMIN')
    if request.method == 'POST':
        from apps.super_admin.models import TerminatedAccount
        
        admin_user.is_active = True
        admin_user.is_terminated = False
        admin_user.terminated_at = None
        admin_user.terminated_by = None
        admin_user.save()
        
        # Reactivate all employee accounts created by this admin
        employees_to_activate = User.objects.filter(employeeprofile__created_by=admin_user)
        for emp in employees_to_activate:
            emp.is_active = True
            emp.is_terminated = False
            emp.terminated_at = None
            emp.terminated_by = None
            emp.save()
            if hasattr(emp, 'employeeprofile'):
                emp.employeeprofile.status = 'ACTIVE'
                emp.employeeprofile.save()
            TerminatedAccount.objects.filter(username=emp.username).delete()
            
        TerminatedAccount.objects.filter(username=admin_user.username).delete()
        
        messages.success(request, f"Admin account '{admin_user.username}' and all associated employee accounts have been activated.")
    return redirect('super_admin:admin_list')

@login_required
@super_admin_required
def company_profile_view(request):
    profile, created = CompanyProfile.objects.get_or_create(id=1)
    form = CompanyProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Company details updated successfully.")
            return redirect('super_admin:company_list')
        else:
            messages.error(request, "Failed to update company profile.")
    return render(request, 'super_admin/company_list.html', {'form': form, 'profile': profile})

@login_required
@super_admin_required
def settings_view(request):
    # Initialize some settings if they don't exist
    settings_keys = [
        ('LATE_THRESHOLD', '09:30', 'Lateness daily clock-in threshold (HH:MM)'),
        ('MIN_WORKING_HOURS', '8.00', 'Minimum hours for a standard full day presence status'),
        ('FACIAL_MATCH_THRESHOLD', '0.80', 'Standard decimal threshold correlation match limit for face engine'),
    ]
    for key, value, desc in settings_keys:
        SystemSetting.objects.get_or_create(key=key, defaults={'value': value, 'description': desc})

    all_settings = SystemSetting.objects.all()
    
    if request.method == 'POST':
        for setting in all_settings:
            val = request.POST.get(setting.key)
            if val is not None:
                setting.value = val
                setting.save()
        messages.success(request, "System settings updated successfully.")
        return redirect('super_admin:settings')

    return render(request, 'super_admin/settings.html', {'settings': all_settings})

@login_required
@admin_required
def request_limit_increase(request):
    if request.method == 'POST':
        requested_limit = request.POST.get('requested_limit')
        reason = request.POST.get('reason')
        
        if not requested_limit or int(requested_limit) <= 0:
            messages.error(request, "Please enter a valid slot limit.")
            return redirect('employee_management:add_employee')
            
        from apps.super_admin.models import LimitRequest
        # Check if there is already a pending request
        if LimitRequest.objects.filter(admin=request.user, status='PENDING').exists():
            messages.error(request, "You already have a pending slot request.")
            return redirect('employee_management:add_employee')
            
        LimitRequest.objects.create(
            admin=request.user,
            requested_limit=int(requested_limit),
            reason=reason
        )
        messages.success(request, "Limit increase request submitted to Super Admin successfully.")
        
    return redirect('employee_management:add_employee')

@login_required
@super_admin_required
def review_limit_requests(request):
    from apps.super_admin.models import LimitRequest
    requests = LimitRequest.objects.all().order_by('-created_at').select_related('admin')
    return render(request, 'super_admin/limit_requests.html', {'limit_requests': requests})

@login_required
@super_admin_required
def approve_limit_request(request, pk):
    from apps.super_admin.models import LimitRequest, AdminLimit
    limit_req = get_object_or_404(LimitRequest, pk=pk, status='PENDING')
    
    if request.method == 'POST':
        # Update AdminLimit
        limit_obj, created = AdminLimit.objects.get_or_create(admin=limit_req.admin)
        limit_obj.max_employees = limit_req.requested_limit
        limit_obj.save()
        
        # Update Request Status
        from django.utils import timezone
        limit_req.status = 'APPROVED'
        limit_req.reviewed_at = timezone.now()
        limit_req.save()
        
        messages.success(request, f"Approved request from '{limit_req.admin.username}'. Employee limit increased to {limit_req.requested_limit}.")
        
    return redirect('super_admin:review_limit_requests')

@login_required
@super_admin_required
def reject_limit_request(request, pk):
    from apps.super_admin.models import LimitRequest
    limit_req = get_object_or_404(LimitRequest, pk=pk, status='PENDING')
    
    if request.method == 'POST':
        from django.utils import timezone
        limit_req.status = 'REJECTED'
        limit_req.reviewed_at = timezone.now()
        limit_req.save()
        
        messages.warning(request, f"Rejected limit increase request from '{limit_req.admin.username}'.")
        
    return redirect('super_admin:review_limit_requests')

@login_required
@super_admin_required
def super_admin_shift_list(request, admin_id):
    from django.http import Http404
    raise Http404("This page is no longer available.")

@login_required
@super_admin_required
def super_admin_shift_create(request, admin_id):
    from django.http import Http404
    raise Http404("This action is no longer available.")

@login_required
@super_admin_required
def super_admin_shift_edit(request, admin_id, pk):
    from django.http import Http404
    raise Http404("This action is no longer available.")

@login_required
@super_admin_required
def super_admin_shift_delete(request, admin_id, pk):
    from django.http import Http404
    raise Http404("This action is no longer available.")

@login_required
@super_admin_required
def super_admin_shift_toggle(request, admin_id, pk):
    from django.http import Http404
    raise Http404("This action is no longer available.")
