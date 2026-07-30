from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import EmployeeProfile
from .forms import EmployeeAddForm, EmployeeEditForm
from apps.accounts.permissions import admin_required, admin_or_super_admin_required

@login_required
@admin_required
def employee_list(request):
    employees = EmployeeProfile.objects.filter(status='ACTIVE', created_by=request.user).select_related('user', 'department')
    return render(request, 'employee_management/employee_list.html', {'employees': employees, 'title_prefix': 'Active'})

@login_required
@admin_required
def inactive_employees(request):
    employees = EmployeeProfile.objects.filter(status='INACTIVE', created_by=request.user).select_related('user', 'department')
    return render(request, 'employee_management/employee_list.html', {'employees': employees, 'title_prefix': 'Inactive'})

@login_required
@admin_required
def add_employee(request):
    from apps.super_admin.models import AdminLimit, LimitRequest
    
    # Enforce limit checking for Admin accounts
    if request.user.role == 'ADMIN':
        limit_obj, created = AdminLimit.objects.get_or_create(admin=request.user, defaults={'max_employees': 5})
        max_employees = limit_obj.max_employees
        created_count = request.user.created_employees.count()
        
        if created_count >= max_employees:
            pending_request = LimitRequest.objects.filter(admin=request.user, status='PENDING').exists()
            return render(request, 'employee_management/limit_reached.html', {
                'max_employees': max_employees,
                'created_count': created_count,
                'pending_request': pending_request
            })
            
    form = EmployeeAddForm(request.POST or None, request.FILES or None, creator=request.user)
    face_error = None
    
    if request.method == 'POST':
        face_images_json = request.POST.get('face_images')
        
        import json
        try:
            face_images = json.loads(face_images_json) if face_images_json else []
        except Exception:
            face_images = []
            
        if form.is_valid():
            # Double check limit in POST
            if request.user.role == 'ADMIN':
                limit_obj, created = AdminLimit.objects.get_or_create(admin=request.user, defaults={'max_employees': 5})
                if request.user.created_employees.count() >= limit_obj.max_employees:
                    messages.error(request, "Limit Reached: You cannot create more employee accounts.")
                    return redirect('employee_management:employee_list')
            
            profile = form.save()
            
            if not face_images or len(face_images) == 0:
                profile.user.delete()
                face_error = "Biometric Face Registration is mandatory. Please scan and verify the employee's face before submitting."
            else:
                from apps.biometric.face_engine import FaceEngine
                from apps.biometric.models import FaceEnrollment, BiometricLog
                from django.core.files.base import ContentFile
                
                engine = FaceEngine()
                all_face_lists = []
                scores = []
                thumbnail_bytes = None
                first_analysis = {}
                
                for idx, base64_image in enumerate(face_images):
                    success, face_list, img_bytes, message, q_score, checks, facial_analysis = engine.register_face(base64_image)
                    if success:
                        all_face_lists.append(face_list)
                        scores.append(q_score)
                        if idx == 0:
                            thumbnail_bytes = img_bytes
                            first_analysis = facial_analysis
                    else:
                        face_error = f"Biometric verification failed on sample {idx + 1}: {message}"
                        break
                
                # Run advanced quality score & anti-spoofing checks if no error yet
                if not face_error and len(all_face_lists) == len(face_images) and len(face_images) > 0:
                    avg_score = sum(scores) / len(scores)
                    if avg_score < 70:
                        face_error = f"Enrollment rejected: Quality score too low ({avg_score:.1f} < 70). Please ensure good lighting and position."
                    
                    if not face_error and len(all_face_lists) > 1:
                        sims_to_first = [engine.compute_similarity(all_face_lists[0], t) for t in all_face_lists[1:]]
                        if len(sims_to_first) > 0:
                            min_sim = min(sims_to_first)
                            if min_sim > 0.97:
                                face_error = "Liveness Verification Failed: No head movement detected (static photo blocked)."
                
                if not face_error and len(all_face_lists) == len(face_images):
                    # Save face data list and thumbnail
                    enrollment, created = FaceEnrollment.objects.get_or_create(user=profile.user)
                    
                    # Store as advanced dictionary mapping
                    from django.utils import timezone
                    avg_score = sum(scores) / len(scores) if scores else 0
                    enrollment_dict = {
                        "templates": all_face_lists,
                        "quality_score": avg_score,
                        "timestamp": timezone.now().isoformat(),
                        "facial_analysis": first_analysis
                    }
                    enrollment.face_data = json.dumps(enrollment_dict)
                    
                    # Save the first sample cropped face image as the enrolled thumbnail
                    if thumbnail_bytes:
                        file_name = f"user_{profile.user.id}_face.jpg"
                        enrollment.enrolled_image.save(file_name, ContentFile(thumbnail_bytes), save=False)
                    
                    enrollment.save()
                    
                    # Create initial audit log if custom timings are provided
                    if profile.custom_check_in_time or profile.custom_check_out_time:
                        from .models import EmployeeTimingAuditLog
                        EmployeeTimingAuditLog.objects.create(
                            employee_profile=profile,
                            employee_id=profile.display_employee_id,
                            employee_name=profile.user.get_full_name() or profile.user.username,
                            previous_check_in_time=None,
                            previous_check_out_time=None,
                            updated_check_in_time=profile.custom_check_in_time,
                            updated_check_out_time=profile.custom_check_out_time,
                            modified_by=request.user
                        )
                    
                    # Auditing Log
                    BiometricLog.objects.create(
                        user=profile.user,
                        action='ENROLL',
                        status='SUCCESS',
                        details=f"Successfully captured and enrolled {len(all_face_lists)} face samples during registration. Quality Score: {avg_score:.1f}. (Action by {request.user.username})"
                    )
                    
                    messages.success(request, f"Employee account and biometric profile ({len(all_face_lists)} samples) for {profile.user.username} have been successfully created.")
                    return redirect('employee_management:employee_list')
                else:
                    # Roll back created profile and user on scan failure
                    profile.user.delete()
                    if not face_error:
                        face_error = "Could not process all face samples successfully."
                    messages.error(request, f"Failed to register employee: {face_error}")
        else:
            messages.error(request, "Failed to create employee. Review form inputs.")
            
    return render(request, 'employee_management/add_employee.html', {
        'form': form,
        'face_error': face_error
    })

@login_required
@admin_required
def edit_employee(request, pk):
    profile = get_object_or_404(EmployeeProfile, pk=pk, created_by=request.user)
    prev_check_in = profile.custom_check_in_time
    prev_check_out = profile.custom_check_out_time
    prev_shift = profile.shift
    
    form = EmployeeEditForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == 'POST':
        if form.is_valid():
            updated_profile = form.save(commit=False)
            new_check_in = updated_profile.custom_check_in_time
            new_check_out = updated_profile.custom_check_out_time
            new_shift = updated_profile.shift
            
            if prev_check_in != new_check_in or prev_check_out != new_check_out:
                from .models import EmployeeTimingAuditLog
                EmployeeTimingAuditLog.objects.create(
                    employee_profile=profile,
                    employee_id=profile.display_employee_id,
                    employee_name=profile.user.get_full_name() or profile.user.username,
                    previous_check_in_time=prev_check_in,
                    previous_check_out_time=prev_check_out,
                    updated_check_in_time=new_check_in,
                    updated_check_out_time=new_check_out,
                    modified_by=request.user
                )
                
            if prev_shift != new_shift:
                from .models import EmployeeShiftAuditLog
                from apps.notifications.models import Notification
                
                EmployeeShiftAuditLog.objects.create(
                    employee_profile=profile,
                    employee_id=profile.display_employee_id,
                    employee_name=profile.user.get_full_name() or profile.user.username,
                    previous_shift=prev_shift,
                    previous_shift_name=prev_shift.name if prev_shift else "None",
                    new_shift=new_shift,
                    new_shift_name=new_shift.name if new_shift else "None",
                    modified_by=request.user
                )
                
                shift_timing_str = f" ({new_shift.start_time.strftime('%H:%M')} - {new_shift.end_time.strftime('%H:%M')})" if new_shift else ""
                new_shift_display = f"'{new_shift.name}'{shift_timing_str}" if new_shift else "None"
                
                Notification.objects.create(
                    recipient=profile.user,
                    title="Shift Assignment Updated",
                    message=f"Your shift assignment has been updated to {new_shift_display}."
                )
            
            updated_profile.save()
            form.save_m2m()
            
            messages.success(request, "Employee details have been successfully updated.")
            return redirect('employee_management:employee_list')
        else:
            messages.error(request, "Failed to update employee details.")
            
    return render(request, 'employee_management/edit_employee.html', {'form': form, 'profile': profile})

@login_required
@admin_required
def employee_details(request, pk):
    profile = get_object_or_404(EmployeeProfile.objects.select_related('user', 'department'), pk=pk, created_by=request.user)
    return render(request, 'employee_management/employee_details.html', {'profile': profile})

@login_required
def employee_monthly_attendance_api(request, pk):
    from django.http import JsonResponse
    from django.utils import timezone
    from datetime import datetime, date, timedelta
    import calendar
    
    profile = get_object_or_404(EmployeeProfile, pk=pk)
    
    # Security: employee can only query their own attendance, admin can query anyone's
    if request.user.role != 'ADMIN' and profile.user != request.user:
        return JsonResponse({'success': False, 'message': 'Permission Denied'}, status=403)
    
    # Get parameters
    year = int(request.GET.get('year', timezone.localdate().year))
    month = int(request.GET.get('month', timezone.localdate().month))
    
    # Get attendance settings of the admin who created the employee
    from apps.attendance.models import AdminAttendanceSettings, AttendanceRecord
    from apps.leave_management.models import LeaveRequest
    
    creator_admin = profile.created_by or request.user
    settings_obj, created = AdminAttendanceSettings.objects.get_or_create(
        admin=creator_admin,
        defaults={
            'check_in_time': datetime.strptime("09:00:00", "%H:%M:%S").time(),
            'check_out_time': datetime.strptime("18:00:00", "%H:%M:%S").time(),
            'working_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            'custom_holidays': []
        }
    )
    
    first_day = date(year, month, 1)
    # Find last day of the month
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)
    
    # Get records
    records = AttendanceRecord.objects.filter(user=profile.user, date__gte=first_day, date__lte=last_day)
    records_dict = {r.date: r for r in records}
    
    # Get leaves
    leaves = LeaveRequest.objects.filter(
        user=profile.user,
        status='APPROVED',
        start_date__lte=last_day,
        end_date__gte=first_day
    )
    
    # Check if a date is inside a leave request
    def is_on_leave(d):
        for lv in leaves:
            if lv.start_date <= d <= lv.end_date:
                return True
        return False
        
    # Standard shift hours
    dummy_in = datetime.combine(first_day, settings_obj.check_in_time)
    dummy_out = datetime.combine(first_day, settings_obj.check_out_time)
    shift_hours = max(1.0, (dummy_out - dummy_in).total_seconds() / 3600.0)
    
    month_days = {}
    
    # Monthly aggregations
    total_working_days = 0
    present_days = 0
    absent_days = 0
    leave_days = 0
    late_arrivals = 0
    total_working_hours = 0.0
    monthly_salary_earned = 0.0
    total_deductions = 0.0
    total_overtime_earnings = 0.0
    
    # Chart data helpers
    daily_hours_list = []
    daily_salary_list = []
    
    current_date = first_day
    while current_date <= last_day:
        weekday_str = current_date.strftime('%A')
        date_str = current_date.strftime('%Y-%m-%d')
        is_holiday_or_weekend = (date_str in settings_obj.custom_holidays)
        
        joining_date = profile.date_of_joining
        base_salary = float(profile.daily_salary) if profile.daily_salary is not None else float(settings_obj.default_daily_salary)
        
        if current_date < joining_date:
            # Day is before the employee's onboarding/joining date
            day_data = {
                'date': date_str,
                'day_name': weekday_str,
                'is_holiday_or_weekend': is_holiday_or_weekend,
                'base_salary': base_salary,
                'status': 'NOT_EMPLOYED',
                'check_in': "--",
                'check_out': "--",
                'total_hours': 0.0,
                'lateness': 0,
                'early_exit': 0,
                'daily_salary': 0.0,
                'deduction': 0.0,
                'overtime_hours': 0.0,
                'overtime_pay': 0.0,
                'net_pay': 0.0,
                'ot_check_in': "--",
                'ot_check_out': "--",
                'ot_amount': 0.0,
            }
            month_days[date_str] = day_data
            
            daily_hours_list.append({
                'date': date_str,
                'hours': 0.0,
                'status': 'NOT_EMPLOYED'
            })
            daily_salary_list.append({
                'date': date_str,
                'net_pay': 0.0
            })
            
            current_date += timedelta(days=1)
            continue
            
        day_data = {
            'date': date_str,
            'day_name': weekday_str,
            'is_holiday_or_weekend': is_holiday_or_weekend,
            'base_salary': base_salary,
        }
        
        if not is_holiday_or_weekend:
            total_working_days += 1
            
        rec = records_dict.get(current_date)
        
        # Check if they have an OvertimeRecord on this day
        from apps.attendance.models import OvertimeRecord
        ot_rec = OvertimeRecord.objects.filter(user=profile.user, date=current_date).first()
        if ot_rec and ot_rec.check_out:
            ot_check_in = timezone.localtime(ot_rec.check_in).strftime('%I:%M %p')
            ot_check_out = timezone.localtime(ot_rec.check_out).strftime('%I:%M %p')
            ot_hours = float(ot_rec.total_hours or 0.0)
            ot_pay = float(ot_rec.calculated_amount or 0.0)
        elif ot_rec:
            ot_check_in = timezone.localtime(ot_rec.check_in).strftime('%I:%M %p')
            ot_check_out = "Active OT"
            ot_hours = 0.0
            ot_pay = 0.0
        else:
            ot_check_in = "--"
            ot_check_out = "--"
            ot_hours = 0.0
            ot_pay = 0.0

        if rec:
            present_days += 1
            if rec.status == 'LATE':
                late_arrivals += 1
                
            check_in_time = timezone.localtime(rec.check_in).strftime('%I:%M %p')
            check_out_time = timezone.localtime(rec.check_out).strftime('%I:%M %p') if rec.check_out else "Active Shift"
            
            if rec.check_out:
                hours = float(rec.total_hours) if rec.total_hours is not None else 0.0
            else:
                delta = timezone.now() - rec.check_in
                hours = round(max(0.0, delta.total_seconds() / 3600.0), 2)
            total_working_hours += hours
            
            lateness = rec.dynamic_lateness_minutes
            early_exit = rec.dynamic_early_checkout_minutes
            daily_salary = float(rec.calculated_salary)
            deduction = max(0.0, base_salary - daily_salary)
            
            # Overtime hours and pay are based on the dedicated OvertimeRecord
            overtime_hours = ot_hours
            overtime_pay = ot_pay
            net_pay = round(daily_salary + overtime_pay, 2)
            
            monthly_salary_earned += daily_salary
            total_deductions += deduction
            total_overtime_earnings += overtime_pay
            
            day_data.update({
                'status': rec.status,
                'check_in': check_in_time,
                'check_out': check_out_time,
                'total_hours': hours,
                'lateness': lateness,
                'early_exit': early_exit,
                'daily_salary': daily_salary,
                'deduction': deduction,
                'overtime_hours': overtime_hours,
                'overtime_pay': overtime_pay,
                'net_pay': net_pay,
                'ot_check_in': ot_check_in,
                'ot_check_out': ot_check_out,
                'ot_amount': overtime_pay,
            })
            
        elif is_on_leave(current_date):
            if not is_holiday_or_weekend:
                leave_days += 1
                
            # Leave days are fully paid
            monthly_salary_earned += base_salary
            
            # Overtime hours and pay
            overtime_hours = ot_hours
            overtime_pay = ot_pay
            net_pay = round(base_salary + overtime_pay, 2)
            total_overtime_earnings += overtime_pay
            
            day_data.update({
                'status': 'ON_LEAVE',
                'check_in': "--",
                'check_out': "--",
                'total_hours': 0.0,
                'lateness': 0,
                'early_exit': 0,
                'daily_salary': base_salary,
                'deduction': 0.0,
                'overtime_hours': overtime_hours,
                'overtime_pay': overtime_pay,
                'net_pay': net_pay,
                'ot_check_in': ot_check_in,
                'ot_check_out': ot_check_out,
                'ot_amount': overtime_pay,
            })
            
        elif is_holiday_or_weekend:
            # Weekend/holiday days are fully paid off-days
            monthly_salary_earned += base_salary
            
            # Overtime hours and pay
            overtime_hours = ot_hours
            overtime_pay = ot_pay
            net_pay = round(base_salary + overtime_pay, 2)
            total_overtime_earnings += overtime_pay
            
            day_data.update({
                'status': 'WEEKEND',
                'check_in': "--",
                'check_out': "--",
                'total_hours': 0.0,
                'lateness': 0,
                'early_exit': 0,
                'daily_salary': base_salary,
                'deduction': 0.0,
                'overtime_hours': overtime_hours,
                'overtime_pay': overtime_pay,
                'net_pay': net_pay,
                'ot_check_in': ot_check_in,
                'ot_check_out': ot_check_out,
                'ot_amount': overtime_pay,
            })
            
        else:
            absent_days += 1
            # Absent days have full deduction
            total_deductions += base_salary
            
            # Overtime hours and pay
            overtime_hours = ot_hours
            overtime_pay = ot_pay
            net_pay = round(0.0 + overtime_pay, 2)
            total_overtime_earnings += overtime_pay
            
            day_data.update({
                'status': 'ABSENT',
                'check_in': "--",
                'check_out': "--",
                'total_hours': 0.0,
                'lateness': 0,
                'early_exit': 0,
                'daily_salary': 0.0,
                'deduction': base_salary,
                'overtime_hours': overtime_hours,
                'overtime_pay': overtime_pay,
                'net_pay': net_pay,
                'ot_check_in': ot_check_in,
                'ot_check_out': ot_check_out,
                'ot_amount': overtime_pay,
            })
            
        month_days[date_str] = day_data
        
        # Populate charts data lists
        daily_hours_list.append({
            'date': date_str,
            'hours': day_data.get('total_hours', 0.0),
            'status': day_data['status']
        })
        daily_salary_list.append({
            'date': date_str,
            'net_pay': day_data.get('net_pay', 0.0)
        })
        
        current_date += timedelta(days=1)
        
    # Final sums
    net_monthly_salary = round(monthly_salary_earned, 2)
    ot_net_monthly_salary = round(total_overtime_earnings, 2)
    grand_total_pay = round(monthly_salary_earned + total_overtime_earnings, 2)
    
    # Calculate attendance percentage
    total_possible_days = present_days + absent_days
    attendance_pct = round((present_days / total_possible_days) * 100, 1) if total_possible_days > 0 else 100.0
    
    analytics = {
        'total_working_days': total_working_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'leave_days': leave_days,
        'late_arrivals': late_arrivals,
        'total_working_hours': round(total_working_hours, 1),
        'monthly_salary_earned': round(monthly_salary_earned, 2),
        'total_deductions': round(total_deductions, 2),
        'total_overtime_earnings': round(total_overtime_earnings, 2),
        'net_monthly_salary': net_monthly_salary,
        'ot_net_monthly_salary': ot_net_monthly_salary,
        'grand_total_pay': grand_total_pay,
        'attendance_pct': attendance_pct,
    }
    
    return JsonResponse({
        'success': True,
        'month_days': month_days,
        'analytics': analytics,
        'charts': {
            'daily_hours': daily_hours_list,
            'daily_salary': daily_salary_list,
        }
    })

@login_required
@admin_required
def delete_employee(request, pk):
    profile = EmployeeProfile.objects.filter(pk=pk, created_by=request.user).first()
    if not profile:
        messages.warning(request, "Employee profile not found or already deleted.")
        return redirect('employee_management:employee_list')
        
    if request.method == 'POST':
        import os
        from django.utils import timezone
        from apps.super_admin.models import TerminatedAccount
        from apps.notifications.models import Notification
        from apps.leave_management.models import LeaveRequest
        from apps.attendance.models import AttendanceRecord, OvertimeRecord, AttendanceLog
        from apps.biometric.models import FaceEnrollment, BiometricLog
        from apps.accounts.models import ForgotPasswordOTP
        
        user = profile.user
        username = user.username
        display_name = user.display_username
        
        # 1. Delete notifications
        Notification.objects.filter(recipient=user).delete()
        
        # 2. Delete leaves
        LeaveRequest.objects.filter(user=user).delete()
        
        # 3. Delete attendance & overtime records
        AttendanceRecord.objects.filter(user=user).delete()
        OvertimeRecord.objects.filter(user=user).delete()
        AttendanceLog.objects.filter(user=user).delete()
        
        # 4. Delete biometric data (with disk files)
        enrollments = FaceEnrollment.objects.filter(user=user)
        for enrollment in enrollments:
            try:
                if enrollment.enrolled_image and os.path.exists(enrollment.enrolled_image.path):
                    os.remove(enrollment.enrolled_image.path)
            except Exception:
                pass
        enrollments.delete()
        BiometricLog.objects.filter(user=user).delete()
        
        # 5. Delete ForgotPasswordOTP
        ForgotPasswordOTP.objects.filter(user=user).delete()
        
        # 6. Delete Employee Profile files and profile itself
        try:
            if profile.profile_image and os.path.exists(profile.profile_image.path):
                os.remove(profile.profile_image.path)
            if profile.document and os.path.exists(profile.document.path):
                os.remove(profile.document.path)
        except Exception:
            pass
        profile.delete()
        
        # 7. Delete User Profile files
        if hasattr(user, 'userprofile'):
            u_prof = user.userprofile
            try:
                if u_prof.avatar and os.path.exists(u_prof.avatar.path):
                    os.remove(u_prof.avatar.path)
            except Exception:
                pass
            u_prof.delete()
            
        # 8. Delete from TerminatedAccount so username is free
        TerminatedAccount.objects.filter(username=username).delete()
        
        # 9. Finally delete the User itself
        user.delete()
        
        messages.success(request, f"Employee '{display_name}' and all associated data have been permanently deleted.")
    return redirect('employee_management:employee_list')

@login_required
@admin_required
def deactivate_employee(request, pk):
    profile = EmployeeProfile.objects.filter(pk=pk, created_by=request.user).first()
    if not profile:
        messages.warning(request, "Employee profile not found.")
        return redirect('employee_management:employee_list')
        
    if request.method == 'POST':
        from django.utils import timezone
        from apps.super_admin.models import TerminatedAccount
        
        user = profile.user
        user.is_active = False
        user.is_terminated = True
        user.terminated_at = timezone.now()
        user.terminated_by = request.user
        user.save()
        
        profile.status = 'INACTIVE'
        profile.save()
        
        # Log to TerminatedAccount
        TerminatedAccount.objects.get_or_create(
            username=user.username,
            defaults={'role': 'EMPLOYEE'}
        )
        
        messages.success(request, f"Employee '{user.get_full_name() or user.username}' has been successfully deactivated.")
    return redirect('employee_management:employee_details', pk=pk)

@login_required
@admin_required
def activate_employee(request, pk):
    profile = EmployeeProfile.objects.filter(pk=pk, created_by=request.user).first()
    if not profile:
        messages.warning(request, "Employee profile not found.")
        return redirect('employee_management:employee_list')
        
    if request.method == 'POST':
        from apps.super_admin.models import TerminatedAccount
        
        user = profile.user
        user.is_active = True
        user.is_terminated = False
        user.terminated_at = None
        user.terminated_by = None
        user.save()
        
        profile.status = 'ACTIVE'
        profile.save()
        
        # Remove from TerminatedAccount
        TerminatedAccount.objects.filter(username=user.username).delete()
        
        messages.success(request, f"Employee '{user.get_full_name() or user.username}' has been successfully activated.")
    return redirect('employee_management:employee_details', pk=pk)

@login_required
@admin_required
def unlock_biometrics(request, pk):
    profile = get_object_or_404(EmployeeProfile, pk=pk, created_by=request.user)
    if request.method == 'POST':
        profile.failed_biometric_attempts = 0
        profile.is_biometric_locked = False
        profile.biometric_lock_reason = None
        profile.save()
        messages.success(request, f"Biometrics for employee '{profile.user.get_full_name() or profile.user.username}' have been successfully unlocked.")
    return redirect('employee_management:employee_details', pk=pk)
