from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.core.files.base import ContentFile
import json
import base64
from datetime import datetime, time
from .models import AttendanceRecord, AttendanceLog, AdminAttendanceSettings, OvertimeRecord
from apps.biometric.models import FaceEnrollment
from apps.biometric.face_engine import FaceEngine
from apps.accounts.permissions import admin_required, employee_required

@login_required
@employee_required
def check_in(request):
    """
    Renders the employee check-in interface.
    """
    today = timezone.localdate()
    already_checked_in = AttendanceRecord.objects.filter(user=request.user, date=today).exists()
    
    # Check if within the check-in window
    matching_date, block_message = get_active_shift_date_for_employee(request.user)
    if not matching_date:
        return render(request, 'attendance/check_in.html', {
            'already_checked_in': already_checked_in,
            'is_blocked': True,
            'block_message': block_message
        })
        
    return render(request, 'attendance/check_in.html', {
        'already_checked_in': already_checked_in,
        'is_blocked': False
    })

def get_active_shift_date_for_employee(employee_user):
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    try:
        profile = employee_user.employeeprofile
        if not profile or not profile.shift:
            return None, "No shift assigned to your profile. Please contact your Admin."
    except Exception:
        return None, "No shift assigned to your profile. Please contact your Admin."
        
    shift = profile.shift
    now = timezone.now()
    local_now = timezone.localtime(now)
    
    # Check all possible offsets: yesterday (-1), today (0), tomorrow (+1)
    matching_date = None
    for offset in [-1, 0, 1]:
        shift_date = local_now.date() + timedelta(days=offset)
        start_time = profile.custom_check_in_time or shift.start_time
        end_time = profile.custom_check_out_time or shift.end_time
        
        shift_start_dt = datetime.combine(shift_date, start_time)
        shift_start_dt = timezone.make_aware(shift_start_dt)
        
        # Cross-midnight shift end calculation
        shift_end_dt = datetime.combine(shift_date, end_time)
        shift_end_dt = timezone.make_aware(shift_end_dt)
        if end_time < start_time:
            shift_end_dt = shift_end_dt + timedelta(days=1)
            
        # Allowed window: starts exactly 30 minutes before shift start and remains active until shift end
        window_start = shift_start_dt - timedelta(minutes=30)
        window_end = shift_end_dt
        
        if window_start <= local_now <= window_end:
            matching_date = shift_date
            break

    if matching_date:
        return matching_date, None
    else:
        return None, "Check-in is not yet available. You can check in 30 minutes before your shift starts."

def check_ot_eligibility(employee_user):
    from django.utils import timezone
    from datetime import datetime, timedelta
    from apps.attendance.models import AttendanceRecord, OvertimeRecord
    
    try:
        profile = employee_user.employeeprofile
        if not profile or not profile.shift:
            return False, "No shift assigned to your profile. Please contact your Admin."
    except Exception:
        return False, "No shift assigned to your profile. Please contact your Admin."
        
    shift = profile.shift
    local_now = timezone.localtime(timezone.now())
    
    # Check both yesterday and today as candidate shift dates
    candidate_dates = [local_now.date(), local_now.date() - timedelta(days=1)]
    
    for shift_date in candidate_dates:
        # Calculate shift end datetime
        start_time = profile.custom_check_in_time or shift.start_time
        end_time = profile.custom_check_out_time or shift.end_time
        
        shift_start_dt = datetime.combine(shift_date, start_time)
        shift_start_dt = timezone.make_aware(shift_start_dt)
        
        shift_end_dt = datetime.combine(shift_date, end_time)
        shift_end_dt = timezone.make_aware(shift_end_dt)
        if end_time < start_time:
            shift_end_dt = shift_end_dt + timedelta(days=1)
            
        # 1. Has the shift ended?
        if local_now < shift_end_dt:
            # Shift is still active, so cannot start OT for this shift date
            continue
            
        # 2. Check if a valid regular attendance record exists for this shift date
        # and has checked out
        reg_record = AttendanceRecord.objects.filter(user=employee_user, date=shift_date).first()
        if not reg_record:
            continue
            
        if not reg_record.check_out:
            continue
            
        # 3. Check for duplicate OT sessions for this shift date
        ot_exists = OvertimeRecord.objects.filter(user=employee_user, date=shift_date).exists()
        if ot_exists:
            continue
            
        # If we reach here, this shift date is eligible for OT check-in!
        return True, shift_date
        
    # Construct a helpful failure message if not eligible
    for shift_date in [local_now.date(), local_now.date() - timedelta(days=1)]:
        shift_start_dt = datetime.combine(shift_date, shift.start_time)
        shift_start_dt = timezone.make_aware(shift_start_dt)
        
        shift_end_dt = datetime.combine(shift_date, shift.end_time)
        shift_end_dt = timezone.make_aware(shift_end_dt)
        if shift.end_time < shift.start_time:
            shift_end_dt = shift_end_dt + timedelta(days=1)
            
        if shift_start_dt - timedelta(minutes=30) <= local_now <= shift_end_dt:
            reg_record = AttendanceRecord.objects.filter(user=employee_user, date=shift_date).first()
            if reg_record and not reg_record.check_out:
                return False, f"OT Check-In is disabled because your regular shift ({shift.name}) is currently active and you haven't checked out yet."
            return False, f"OT Check-In is disabled because your regular shift ({shift.name}) is currently active."
            
    # Check if duplicate OT today
    if OvertimeRecord.objects.filter(user=employee_user, date=local_now.date()).exists():
        return False, "You have already completed an OT session for today."
        
    # Check if they have not checked out of regular shift
    reg_record_today = AttendanceRecord.objects.filter(user=employee_user, date=local_now.date()).first()
    if not reg_record_today:
        return False, "You must check in and check out of your regular shift before starting OT."
    if not reg_record_today.check_out:
        return False, "You must check out of your regular shift before starting OT."
        
    return False, "Overtime check-in is not available. Please verify your shift status and check-out records."

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_facial_match_threshold():
    from apps.super_admin.models import SystemSetting
    try:
        threshold_setting = SystemSetting.objects.get(key='FACIAL_MATCH_THRESHOLD')
        return float(threshold_setting.value)
    except Exception:
        return 0.74

def handle_failed_biometric_attempt(user, action, ip_addr, user_agent, failure_reason, details, similarity=None):
    try:
        profile = user.employeeprofile
        emp_id = profile.display_employee_id
        emp_name = user.get_full_name() or user.username
        profile.failed_biometric_attempts += 1
        profile.is_biometric_locked = False
        profile.save()
        attempts = profile.failed_biometric_attempts
    except Exception:
        emp_id = "N/A"
        emp_name = user.get_full_name() or user.username
        attempts = 1

    AttendanceLog.objects.create(
        user=user,
        employee_id=emp_id,
        employee_name=emp_name,
        action=action,
        status='FAILURE',
        ip_address=ip_addr,
        device_info=user_agent,
        failure_reason=failure_reason,
        failed_attempts_count=attempts,
        details=details,
        similarity_score=similarity
    )
    return False

def perform_face_verification(request, action, images_list):
    """
    Analyzes a list of live base64 clips/frames end-to-end.
    Compares against the registered biometric face.
    If the best matching frame has similarity >= 0.75, returns success.
    Also handles proxy detection and locks accounts if necessary.
    """
    from apps.biometric.models import FaceEnrollment
    from apps.biometric.face_engine import FaceEngine
    import numpy as np
    import json
    
    ip_addr = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown Device')
    
    # 1. Fetch registered face templates for the logged-in user
    try:
        logged_in_enrollment = FaceEnrollment.objects.get(user=request.user)
        logged_in_data = json.loads(logged_in_enrollment.face_data)
        if isinstance(logged_in_data, dict):
            logged_in_data = logged_in_data.get('templates', [])
    except FaceEnrollment.DoesNotExist:
        handle_failed_biometric_attempt(
            request.user, action, ip_addr, user_agent,
            "No registered face profile found",
            "Biometric templates not registered for this account."
        )
        return {
            'success': False,
            'message': 'Biometric templates not found. Please contact an admin.'
        }

    engine = FaceEngine()
    best_similarity = -1.0
    best_matching_image = None
    best_matching_bbox = None
    best_matching_report = None
    best_face_normalized = None
    best_quality_checks = None
    best_quality_msg = None
    
    # We will analyze all live clips
    valid_face_frames_count = 0
    
    # Determine creator admin for proxy checks
    try:
        creator_admin = request.user.employeeprofile.created_by
    except Exception:
        creator_admin = None
        
    if creator_admin:
        all_enrollments = FaceEnrollment.objects.filter(
            user__employeeprofile__created_by=creator_admin
        ).exclude(user=request.user).select_related('user')
    else:
        all_enrollments = FaceEnrollment.objects.exclude(user=request.user).select_related('user')

    # Analyze each of the live clips
    for base64_image in images_list:
        if not base64_image:
            continue
            
        try:
            img = engine.decode_base64_image(base64_image)
            face_normalized, bbox = engine.extract_face(img, align=True)
            face_unaligned, _ = engine.extract_face(img, align=False)
        except Exception:
            continue
            
        if face_normalized is None:
            continue
            
        valid_face_frames_count += 1
        
        # Run advanced quality analysis
        is_ok, quality_msg, q_score, checks = engine.validate_face_quality(img, face_normalized, bbox)
        if not is_ok:
            if best_similarity < 0:
                best_quality_msg = quality_msg
                best_quality_checks = checks
            continue
            
        # Calculate similarity with logged-in user's templates
        logged_in_raw = json.loads(logged_in_enrollment.face_data)
        
        # Aligned match similarity
        if len(logged_in_data) > 0 and isinstance(logged_in_data[0], list):
            sims_aligned = [engine.compute_similarity(face_normalized, np.array(t, dtype=np.uint8)) for t in logged_in_data]
            sim_aligned = max(sims_aligned)
        else:
            sim_aligned = engine.compute_similarity(face_normalized, np.array(logged_in_data, dtype=np.uint8))
        report_aligned = engine.get_matching_details(face_normalized, bbox, logged_in_raw, sim_aligned)
        sim_aligned = report_aligned.get('composite_similarity', sim_aligned)

        # Unaligned match similarity
        if face_unaligned is not None:
            if len(logged_in_data) > 0 and isinstance(logged_in_data[0], list):
                sims_unaligned = [engine.compute_similarity(face_unaligned, np.array(t, dtype=np.uint8)) for t in logged_in_data]
                sim_unaligned = max(sims_unaligned)
            else:
                sim_unaligned = engine.compute_similarity(face_unaligned, np.array(logged_in_data, dtype=np.uint8))
            report_unaligned = engine.get_matching_details(face_unaligned, bbox, logged_in_raw, sim_unaligned)
            sim_unaligned = report_unaligned.get('composite_similarity', sim_unaligned)
        else:
            sim_unaligned = 0.0
            report_unaligned = {}

        if sim_aligned >= sim_unaligned:
            logged_in_similarity = sim_aligned
            matching_report = report_aligned
        else:
            logged_in_similarity = sim_unaligned
            matching_report = report_unaligned
            
        # Proxy detection check for this frame
        better_match_user = None
        best_other_similarity = -1.0

        for enrollment in all_enrollments:
            try:
                other_raw = json.loads(enrollment.face_data)
                other_data = other_raw
                if isinstance(other_raw, dict):
                    other_data = other_raw.get('templates', [])
                    
                if len(other_data) > 0 and isinstance(other_data[0], list):
                    other_sims = [engine.compute_similarity(face_normalized, np.array(t, dtype=np.uint8)) for t in other_data]
                    other_sim_aligned = max(other_sims)
                else:
                    other_sim_aligned = engine.compute_similarity(face_normalized, np.array(other_data, dtype=np.uint8))
                other_sim_aligned = engine.compute_composite_similarity(face_normalized, bbox, other_raw, other_sim_aligned)

                if face_unaligned is not None:
                    if len(other_data) > 0 and isinstance(other_data[0], list):
                        other_sims_un = [engine.compute_similarity(face_unaligned, np.array(t, dtype=np.uint8)) for t in other_data]
                        other_sim_unaligned = max(other_sims_un)
                    else:
                        other_sim_unaligned = engine.compute_similarity(face_unaligned, np.array(other_data, dtype=np.uint8))
                    other_sim_unaligned = engine.compute_composite_similarity(face_unaligned, bbox, other_raw, other_sim_unaligned)
                else:
                    other_sim_unaligned = 0.0

                other_sim = max(other_sim_aligned, other_sim_unaligned)
                if other_sim > best_other_similarity:
                    best_other_similarity = other_sim
                    better_match_user = enrollment.user
            except Exception:
                continue

        if best_other_similarity >= 0.58 and best_other_similarity > logged_in_similarity:
            is_locked = handle_failed_biometric_attempt(
                request.user, action, ip_addr, user_agent,
                f"Proxy Blocked: matched '{better_match_user.username}' better than logged-in user",
                f"Proxy Blocked: Face matched '{better_match_user.username}' (Similarity: {best_other_similarity:.2f}) instead of logged-in user '{request.user.username}' (Similarity: {logged_in_similarity:.2f}).",
                similarity=best_other_similarity
            )
            msg = "Face Verification Failed. Attendance Not Recorded."
            if is_locked:
                msg += " Account has been locked due to too many failed attempts."
            return {
                'success': False,
                'message': msg
            }

        # Keep the best matching frame
        if logged_in_similarity > best_similarity:
            best_similarity = logged_in_similarity
            best_matching_image = base64_image
            best_matching_bbox = bbox
            best_matching_report = matching_report
            best_face_normalized = face_normalized

    # If no face was found or successfully decoded in any of the clips
    if valid_face_frames_count == 0:
        is_locked = handle_failed_biometric_attempt(
            request.user, action, ip_addr, user_agent,
            "No face detected in camera frame",
            "Face detection failed during verification scan."
        )
        msg = "Face Verification Failed. Attendance Not Recorded."
        if is_locked:
            msg += " Account has been locked due to too many failed attempts."
        return {
            'success': False,
            'message': msg
        }

    # If we had faces, but they failed the quality check
    if best_similarity < 0:
        is_locked = handle_failed_biometric_attempt(
            request.user, action, ip_addr, user_agent,
            f"Quality Check Failed: {best_quality_msg}",
            f"Verification photo failed quality check: {best_quality_msg}. Checks: {json.dumps(best_quality_checks)}",
            similarity=None
        )
        msg = "Face verification failed. Please try again with proper lighting and camera positioning."
        if is_locked:
            msg += " Account has been locked due to too many failed attempts."
        return {
            'success': False,
            'message': msg
        }

    # Enforce match threshold: >= 0.75
    if best_similarity < 0.75:
        is_locked = handle_failed_biometric_attempt(
            request.user, action, ip_addr, user_agent,
            "Biometric Mismatch: face does not match owner",
            f"Face match failed: similarity {best_similarity:.2f} is below threshold 0.75. Match Report: {json.dumps(best_matching_report)}",
            similarity=best_similarity
        )
        msg = "Face verification failed. Please try again with proper lighting and camera positioning."
        if is_locked:
            msg += " Account has been locked due to too many failed attempts."
        return {
            'success': False,
            'message': msg
        }

    # Success! Return the details of the best matching frame
    return {
        'success': True,
        'similarity_score': best_similarity,
        'image': best_matching_image,
        'bbox': best_matching_bbox,
        'matching_report': best_matching_report,
        'face_normalized': best_face_normalized
    }

@login_required
@employee_required
def check_in_api(request):
    """
    Processes face scanning base64 payloads to log Check-In events with proxy prevention.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP method.'})

    now = timezone.now()
    local_now = timezone.localtime(now)

    ip_addr = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown Device')

    # Lockout Check
    try:
        profile = request.user.employeeprofile
        if profile.is_biometric_locked:
            return JsonResponse({
                'success': False,
                'message': 'Account Biometrically Locked: Too many failed face scans. Please contact your Admin for review and unlock.'
            })
    except Exception:
        profile = None

    if not profile or not profile.shift:
        return JsonResponse({
            'success': False,
            'message': 'Attendance blocked: No shift assigned to your profile. Please contact your Admin.'
        })
    shift = profile.shift

    # Shift Window Check
    matching_date, block_message = get_active_shift_date_for_employee(request.user)
    if not matching_date:
        return JsonResponse({
            'success': False,
            'message': block_message
        })

    try:
        data = json.loads(request.body)
        images_list = data.get('images', [])
        base64_image = data.get('image')
        if not images_list and base64_image:
            images_list = [base64_image]
            
        if not images_list:
            return JsonResponse({'success': False, 'message': 'Camera frame missing.'})

        # Run face recognition on the frames using helper
        verification_result = perform_face_verification(request, 'CHECK_IN', images_list)
        if not verification_result['success']:
            return JsonResponse(verification_result)

        logged_in_similarity = verification_result['similarity_score']
        base64_image = verification_result['image']
        bbox = verification_result['bbox']
        matching_report = verification_result['matching_report']
        face_normalized = verification_result['face_normalized']

        # Otherwise, proceed with successful check-in
        now = timezone.now()
        today = timezone.localdate()

        # Prevent duplicate records
        if AttendanceRecord.objects.filter(user=request.user, date=matching_date).exists():
            return JsonResponse({'success': False, 'message': f'Already checked in for shift date {matching_date}.'})

        # Lateness calculation based on custom or shift start time
        start_time = profile.custom_check_in_time or shift.start_time
        end_time = profile.custom_check_out_time or shift.end_time

        shift_start_dt = datetime.combine(matching_date, start_time)
        shift_start_dt = timezone.make_aware(shift_start_dt)
        
        lateness_minutes = 0
        status = 'PRESENT'
        
        if local_now > shift_start_dt:
            delta = local_now - shift_start_dt
            lateness_minutes = int(delta.total_seconds() / 60)
            status = 'LATE'

        record = AttendanceRecord(
            user=request.user,
            date=matching_date,
            check_in=now,
            status=status,
            lateness_minutes=lateness_minutes,
            similarity_score=logged_in_similarity,
            shift=shift,
            shift_name=shift.name,
            shift_start_time=start_time,
            shift_end_time=end_time
        )
        
        # Decode and save the check-in image
        if base64_image:
            try:
                format, imgstr = base64_image.split(';base64,')
                ext = format.split('/')[-1]
                img_file = ContentFile(base64.b64decode(imgstr), name=f"{request.user.username}_in_{matching_date}.{ext}")
                record.check_in_image = img_file
            except Exception:
                pass
                
        record.save()

        # Reset failed attempts on success
        if profile:
            profile.failed_biometric_attempts = 0
            profile.save()

        # Write logs
        try:
            profile_obj = request.user.employeeprofile
            emp_id = profile_obj.display_employee_id
            emp_name = request.user.get_full_name() or request.user.username
        except Exception:
            emp_id = "N/A"
            emp_name = request.user.get_full_name() or request.user.username

        # Extract detailed facial geometry and landmark analysis on success
        try:
            facial_analysis = engine.analyze_facial_features(face_normalized, bbox)
            details_str = f"Verification successful (Similarity: {logged_in_similarity:.2f}). Logged as {status}. Features: {json.dumps(facial_analysis)}. Match Report: {json.dumps(matching_report)}"
        except Exception:
            details_str = f"Verification successful (Similarity: {logged_in_similarity:.2f}). Logged as {status}. Match Report: {json.dumps(matching_report)}"

        AttendanceLog.objects.create(
            user=request.user,
            employee_id=emp_id,
            employee_name=emp_name,
            action='CHECK_IN',
            status='SUCCESS',
            ip_address=ip_addr,
            device_info=user_agent,
            similarity_score=logged_in_similarity,
            details=details_str
        )
        return JsonResponse({'success': True, 'message': f"Clock-in successful at {local_now.strftime('%H:%M:%S')}."})

    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Server error: {str(e)}"})

@login_required
@employee_required
def check_out(request):
    """
    Renders the employee check-out interface.
    """
    today = timezone.localdate()
    record = AttendanceRecord.objects.filter(user=request.user, date=today).first()
    
    context = {
        'checked_in': record is not None,
        'already_checked_out': record.check_out is not None if record else False
    }
    return render(request, 'attendance/check_out.html', context)

@login_required
@employee_required
def check_out_api(request):
    """
    Processes face scanning base64 payloads to log Check-Out events with proxy prevention.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP method.'})

    ip_addr = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown Device')

    # Lockout Check
    try:
        profile = request.user.employeeprofile
        if profile.is_biometric_locked:
            return JsonResponse({
                'success': False,
                'message': 'Account Biometrically Locked: Too many failed face scans. Please contact your Admin for review and unlock.'
            })
    except Exception:
        profile = None

    try:
        data = json.loads(request.body)
        images_list = data.get('images', [])
        base64_image = data.get('image')
        if not images_list and base64_image:
            images_list = [base64_image]
            
        if not images_list:
            return JsonResponse({'success': False, 'message': 'Camera frame missing.'})

        # Run face recognition on the frames using helper
        verification_result = perform_face_verification(request, 'CHECK_OUT', images_list)
        if not verification_result['success']:
            return JsonResponse(verification_result)

        logged_in_similarity = verification_result['similarity_score']
        base64_image = verification_result['image']
        bbox = verification_result['bbox']
        matching_report = verification_result['matching_report']
        face_normalized = verification_result['face_normalized']

        # Otherwise, proceed with successful check-out
        now = timezone.now()
        today = timezone.localdate()

        # Verify active check-in exists
        record = AttendanceRecord.objects.filter(user=request.user, check_out__isnull=True).order_by('-check_in').first()
        if not record:
            return JsonResponse({'success': False, 'message': 'No active check-in record found. Please check in first.'})

        # Calculate total hours
        delta = now - record.check_in
        total_hours = round(delta.total_seconds() / 3600.0, 2)

        # Check for early check-out based on assigned shift or fallback settings
        from datetime import datetime, timedelta
        local_now = timezone.localtime(now)
        early_checkout_minutes = 0
        is_early = False
        
        if record.shift_end_time:
            shift_end_dt = datetime.combine(record.date, record.shift_end_time)
            shift_end_dt = timezone.make_aware(shift_end_dt)
            if record.shift_end_time < record.shift_start_time:
                shift_end_dt = shift_end_dt + timedelta(days=1)
                
            if local_now < shift_end_dt:
                delta_early = shift_end_dt - local_now
                early_checkout_minutes = int(delta_early.total_seconds() / 60)
                is_early = True
        else:
            try:
                creator_admin = request.user.employeeprofile.created_by
            except Exception:
                creator_admin = None
            if creator_admin:
                settings_obj, created = AdminAttendanceSettings.objects.get_or_create(
                    admin=creator_admin,
                    defaults={
                        'check_in_time': time(9, 0),
                        'check_out_time': time(18, 0),
                        'working_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                    }
                )
                shift_check_out = settings_obj.check_out_time
                if local_now.time() < shift_check_out:
                    dummy_now = datetime.combine(local_now.date(), local_now.time())
                    dummy_shift = datetime.combine(local_now.date(), shift_check_out)
                    delta_early = dummy_shift - dummy_now
                    early_checkout_minutes = int(delta_early.total_seconds() / 60)
                    is_early = True

        # Calculate shift duration to determine if it is a HALF_DAY
        shift_duration_hours = 8.0
        if record.shift_start_time and record.shift_end_time:
            dummy_in = datetime.combine(record.date, record.shift_start_time)
            dummy_out = datetime.combine(record.date, record.shift_end_time)
            if record.shift_end_time < record.shift_start_time:
                dummy_out = dummy_out + timedelta(days=1)
            shift_duration_hours = (dummy_out - dummy_in).total_seconds() / 3600.0
            
        status = record.status
        if total_hours < (shift_duration_hours / 2.0):
            status = 'HALF_DAY'

        record.check_out = now
        record.total_hours = total_hours
        record.is_early_checkout = is_early
        record.early_checkout_minutes = early_checkout_minutes
        record.status = status
        
        # Decode and save the check-out image
        if base64_image:
            try:
                format, imgstr = base64_image.split(';base64,')
                ext = format.split('/')[-1]
                img_file = ContentFile(base64.b64decode(imgstr), name=f"{request.user.username}_out_{record.date}.{ext}")
                record.check_out_image = img_file
            except Exception:
                pass
                
        record.save()

        # Reset failed attempts on success
        if profile:
            profile.failed_biometric_attempts = 0
            profile.save()

        # Write logs
        try:
            profile_obj = request.user.employeeprofile
            emp_id = profile_obj.display_employee_id
            emp_name = request.user.get_full_name() or request.user.username
        except Exception:
            emp_id = "N/A"
            emp_name = request.user.get_full_name() or request.user.username

        # Extract detailed facial geometry and landmark analysis on success
        try:
            facial_analysis = engine.analyze_facial_features(face_normalized, bbox)
            details_str = f"Verification successful (Similarity: {logged_in_similarity:.2f}). Total hours logged: {total_hours}. Features: {json.dumps(facial_analysis)}. Match Report: {json.dumps(matching_report)}"
        except Exception:
            details_str = f"Verification successful (Similarity: {logged_in_similarity:.2f}). Total hours logged: {total_hours}. Match Report: {json.dumps(matching_report)}"

        AttendanceLog.objects.create(
            user=request.user,
            employee_id=emp_id,
            employee_name=emp_name,
            action='CHECK_OUT',
            status='SUCCESS',
            ip_address=ip_addr,
            device_info=user_agent,
            similarity_score=logged_in_similarity,
            details=details_str
        )
        return JsonResponse({'success': True, 'message': f"Clock-out successful at {timezone.localtime(now).strftime('%H:%M:%S')}."})

    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Server error: {str(e)}"})

@login_required
@employee_required
def ot_check_in(request):
    """
    Renders the employee overtime check-in interface.
    """
    # Check if they have an active (unchecked-out) OT record
    active_ot = OvertimeRecord.objects.filter(user=request.user, check_out__isnull=True).first()
    if active_ot:
        return redirect('attendance:ot_check_out')

    eligible, result = check_ot_eligibility(request.user)
    if not eligible:
        return render(request, 'attendance/ot_check_in.html', {
            'is_blocked': True,
            'block_message': result
        })
        
    return render(request, 'attendance/ot_check_in.html', {
        'is_blocked': False,
        'shift_date': result.strftime('%Y-%m-%d')
    })

@login_required
@employee_required
def ot_check_out(request):
    """
    Renders the employee overtime check-out interface.
    """
    from datetime import timedelta
    # Find any active OT check-in (where check_out is None)
    ot_record = OvertimeRecord.objects.filter(user=request.user, check_out__isnull=True).first()
    has_active_ot_checkin = ot_record is not None
    
    already_checked_out = False
    if not has_active_ot_checkin:
        local_now = timezone.localtime(timezone.now())
        candidate_dates = [local_now.date(), local_now.date() - timedelta(days=1)]
        already_checked_out = OvertimeRecord.objects.filter(
            user=request.user,
            date__in=candidate_dates,
            check_out__isnull=False
        ).exists()
    
    context = {
        'has_active_ot_checkin': has_active_ot_checkin,
        'ot_record': ot_record,
        'already_checked_out': already_checked_out
    }
    return render(request, 'attendance/ot_check_out.html', context)

@login_required
@employee_required
def ot_check_in_api(request):
    """
    Processes face scanning base64 payloads to log OT Check-In events.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP method.'})

    # Check OT eligibility using helper function
    eligible, result = check_ot_eligibility(request.user)
    if not eligible:
        return JsonResponse({
            'success': False,
            'message': result
        })
    ot_date = result

    ip_addr = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown Device')

    try:
        data = json.loads(request.body)
        images_list = data.get('images', [])
        base64_image = data.get('image')
        if not images_list and base64_image:
            images_list = [base64_image]
            
        if not images_list:
            return JsonResponse({'success': False, 'message': 'Camera frame missing.'})

        # Run face recognition on the frames using helper
        verification_result = perform_face_verification(request, 'OT_CHECK_IN', images_list)
        if not verification_result['success']:
            return JsonResponse(verification_result)

        logged_in_similarity = verification_result['similarity_score']
        base64_image = verification_result['image']
        bbox = verification_result['bbox']
        matching_report = verification_result['matching_report']
        face_normalized = verification_result['face_normalized']
        engine = FaceEngine()

        # Otherwise, proceed with successful OT check-in
        now = timezone.now()

        try:
            profile = request.user.employeeprofile
            ot_rate = profile.ot_hourly_rate
            if not ot_rate or ot_rate == 0.00:
                creator_admin = profile.created_by
                if creator_admin:
                    ot_rate = creator_admin.attendance_settings.default_ot_hourly_rate
                else:
                    ot_rate = 150.00
        except Exception:
            profile = None
            ot_rate = 150.00

        emp_id = profile.display_employee_id if profile else "N/A"
        emp_name = request.user.get_full_name() or request.user.username
        assigned_shift = profile.shift if profile else None
        shift_end_time = (profile.custom_check_out_time or profile.shift.end_time) if (profile and profile.shift) else None

        record = OvertimeRecord(
            user=request.user,
            date=ot_date,
            check_in=now,
            hourly_rate=ot_rate,
            similarity_score=logged_in_similarity,
            employee_id=emp_id,
            employee_name=emp_name,
            assigned_shift=assigned_shift,
            shift_end_time=shift_end_time,
            ot_status='APPROVED'
        )
        
        # Decode and save the image
        if base64_image:
            try:
                format, imgstr = base64_image.split(';base64,')
                ext = format.split('/')[-1]
                img_file = ContentFile(base64.b64decode(imgstr), name=f"{request.user.username}_ot_in_{ot_date}.{ext}")
                record.check_in_image = img_file
            except Exception:
                pass
                
        record.save()

        # Write logs
        try:
            profile_obj = request.user.employeeprofile
            emp_id = profile_obj.display_employee_id
            emp_name = request.user.get_full_name() or request.user.username
        except Exception:
            emp_id = "N/A"
            emp_name = request.user.get_full_name() or request.user.username

        # Extract detailed facial geometry and landmark analysis on success
        try:
            facial_analysis = engine.analyze_facial_features(face_normalized, bbox)
            details_str = f"OT Verification successful (Similarity: {logged_in_similarity:.2f}). Features: {json.dumps(facial_analysis)}. Match Report: {json.dumps(matching_report)}"
        except Exception:
            details_str = f"OT Verification successful (Similarity: {logged_in_similarity:.2f}). Match Report: {json.dumps(matching_report)}"

        AttendanceLog.objects.create(
            user=request.user,
            employee_id=emp_id,
            employee_name=emp_name,
            action='CHECK_IN',
            status='SUCCESS',
            ip_address=ip_addr,
            device_info=user_agent,
            similarity_score=logged_in_similarity,
            details=details_str
        )
        return JsonResponse({'success': True, 'message': f"OT Clock-in successful at {timezone.localtime(now).strftime('%H:%M:%S')}."})

    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Server error: {str(e)}"})

@login_required
@employee_required
def ot_check_out_api(request):
    """
    Processes face scanning base64 payloads to log OT Check-Out events.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP method.'})



    ip_addr = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown Device')

    try:
        data = json.loads(request.body)
        images_list = data.get('images', [])
        base64_image = data.get('image')
        if not images_list and base64_image:
            images_list = [base64_image]
            
        if not images_list:
            return JsonResponse({'success': False, 'message': 'Camera frame missing.'})

        # Run face recognition on the frames using helper
        verification_result = perform_face_verification(request, 'OT_CHECK_OUT', images_list)
        if not verification_result['success']:
            return JsonResponse(verification_result)

        logged_in_similarity = verification_result['similarity_score']
        base64_image = verification_result['image']
        bbox = verification_result['bbox']
        matching_report = verification_result['matching_report']
        face_normalized = verification_result['face_normalized']
        engine = FaceEngine()

        # Otherwise, proceed with successful OT check-out
        now = timezone.now()
        today = timezone.localdate()

        # Verify active OT check-in exists
        record = OvertimeRecord.objects.filter(user=request.user, check_out__isnull=True).first()
        if not record:
            return JsonResponse({'success': False, 'message': 'No active OT check-in record found.'})

        # Calculate OT hours and OT Pay
        delta = now - record.check_in
        total_hours = round(delta.total_seconds() / 3600.0, 2)
        calculated_amount = round(float(total_hours) * float(record.hourly_rate), 2)

        record.check_out = now
        record.total_hours = total_hours
        record.calculated_amount = calculated_amount
        record.similarity_score = logged_in_similarity

        # Decode and save the check-out image
        if base64_image:
            try:
                format, imgstr = base64_image.split(';base64,')
                ext = format.split('/')[-1]
                img_file = ContentFile(base64.b64decode(imgstr), name=f"{request.user.username}_ot_out_{record.date}.{ext}")
                record.check_out_image = img_file
            except Exception:
                pass
                
        record.save()

        # Write logs
        try:
            profile_obj = request.user.employeeprofile
            emp_id = profile_obj.display_employee_id
            emp_name = request.user.get_full_name() or request.user.username
        except Exception:
            emp_id = "N/A"
            emp_name = request.user.get_full_name() or request.user.username

        # Extract detailed facial geometry and landmark analysis on success
        try:
            facial_analysis = engine.analyze_facial_features(face_normalized, bbox)
            details_str = f"OT Verification successful (Similarity: {logged_in_similarity:.2f}). Total OT hours logged: {total_hours}. Features: {json.dumps(facial_analysis)}. Match Report: {json.dumps(matching_report)}"
        except Exception:
            details_str = f"OT Verification successful (Similarity: {logged_in_similarity:.2f}). Total OT hours logged: {total_hours}. Match Report: {json.dumps(matching_report)}"

        AttendanceLog.objects.create(
            user=request.user,
            employee_id=emp_id,
            employee_name=emp_name,
            action='CHECK_OUT',
            status='SUCCESS',
            ip_address=ip_addr,
            device_info=user_agent,
            similarity_score=logged_in_similarity,
            details=details_str
        )
        return JsonResponse({'success': True, 'message': f"OT Clock-out successful at {timezone.localtime(now).strftime('%H:%M:%S')}."})

    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Server error: {str(e)}"})

@login_required
def attendance_history(request):
    """
    Renders attendance logs for the logged-in Employee.
    """
    records = AttendanceRecord.objects.filter(user=request.user).order_by('-date')
    history_list = []
    for r in records:
        ot = OvertimeRecord.objects.filter(user=request.user, date=r.date).first()
        history_list.append({
            'record': r,
            'ot_check_in': timezone.localtime(ot.check_in).strftime('%I:%M %p') if (ot and ot.check_in) else "--",
            'ot_check_out': timezone.localtime(ot.check_out).strftime('%I:%M %p') if (ot and ot.check_out) else "--",
            'ot_amount': ot.calculated_amount if (ot and ot.check_out) else 0.00
        })
    return render(request, 'attendance/attendance_history.html', {'history_list': history_list})

@login_required
@admin_required
def attendance_logs(request):
    """
    Renders audit logs for Admins. Isolated by creator.
    Includes daily payroll sheet with lateness and custom holiday calculations.
    """
    from apps.employee_management.models import EmployeeProfile
    import json
    from datetime import date
    
    logs = AttendanceLog.objects.filter(user__employeeprofile__created_by=request.user).select_related('user')
    records = AttendanceRecord.objects.filter(user__employeeprofile__created_by=request.user).select_related('user', 'user__employeeprofile')
    
    # Build daily records list with OT data
    daily_records_list = []
    for r in records:
        ot = OvertimeRecord.objects.filter(user=r.user, date=r.date).first()
        ot_hours = ot.total_hours if (ot and ot.check_out) else None
        ot_amount = ot.calculated_amount if (ot and ot.check_out) else None
        daily_records_list.append({
            'record': r,
            'ot_hours': ot_hours,
            'ot_amount': ot_amount,
            'ot_record': ot
        })
    
    # Date filter for daily payroll sheet (default to today)
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    # Retrieve admin settings
    try:
        settings_obj = request.user.attendance_settings
        working_days = settings_obj.working_days
        custom_holidays = settings_obj.custom_holidays
        default_salary = float(settings_obj.default_daily_salary)
    except Exception:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        custom_holidays = []
        default_salary = 1000.00

    selected_date_str = selected_date.strftime('%Y-%m-%d')
    is_holiday_or_weekend = (selected_date_str in custom_holidays)

    # Fetch all active employees created by this admin
    employees = EmployeeProfile.objects.filter(status='ACTIVE', created_by=request.user).select_related('user', 'department')
    
    # Build daily payroll list
    from apps.leave_management.models import LeaveRequest
    daily_payroll_sheet = []
    for emp in employees:
        rec = AttendanceRecord.objects.filter(user=emp.user, date=selected_date).first()
        base_salary = float(emp.daily_salary) if emp.daily_salary is not None else default_salary
        
        # Check if they have an approved leave covering this day
        approved_leave = LeaveRequest.objects.filter(
            user=emp.user,
            status='APPROVED',
            start_date__lte=selected_date,
            end_date__gte=selected_date
        ).first()

        # Check if they have an OvertimeRecord today
        ot_rec = OvertimeRecord.objects.filter(user=emp.user, date=selected_date).first()
        if ot_rec and ot_rec.check_out:
            ot_hours = float(ot_rec.total_hours or 0)
            ot_amount = float(ot_rec.calculated_amount or 0)
        else:
            ot_hours = 0.0
            ot_amount = 0.0

        if rec:
            paid_salary = float(rec.calculated_salary)
            status_display = rec.get_status_display()
            if rec.is_early_checkout:
                status_display += " (Early Check-out)"
            check_in_time = timezone.localtime(rec.check_in).strftime('%H:%M:%S')
            check_out_time = timezone.localtime(rec.check_out).strftime('%H:%M:%S') if rec.check_out else "--"
            total_hours = rec.total_hours
            late_m = rec.dynamic_lateness_minutes
            early_m = rec.dynamic_early_checkout_minutes
        else:
            check_in_time = "--"
            check_out_time = "--"
            total_hours = "--"
            late_m = 0
            early_m = 0
            if approved_leave:
                paid_salary = base_salary
                status_display = f"Leave ({approved_leave.get_leave_type_display()})"
            elif is_holiday_or_weekend:
                paid_salary = base_salary
                status_display = "Holiday / Off-day"
            else:
                paid_salary = 0.00
                status_display = "Absent / Leave"
                
        daily_payroll_sheet.append({
            'employee': emp,
            'check_in': check_in_time,
            'check_out': check_out_time,
            'total_hours': total_hours,
            'status': status_display,
            'base_salary': base_salary,
            'paid_salary': paid_salary + ot_amount,
            'late_minutes': late_m,
            'early_minutes': early_m,
            'ot_hours': ot_hours,
            'ot_amount': ot_amount
        })

    context = {
        'logs': logs,
        'records': records,
        'daily_records_list': daily_records_list,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'daily_payroll_sheet': daily_payroll_sheet,
        'is_holiday_or_weekend': is_holiday_or_weekend
    }
    return render(request, 'attendance/attendance_logs.html', context)

@login_required
@admin_required
def attendance_settings_view(request):
    """
    Renders shift timings, weekly working days, and a monthly holidays calendar configuration.
    """
    from .forms import AdminAttendanceSettingsForm
    from .models import AdminAttendanceSettings
    import json
    
    settings_obj, created = AdminAttendanceSettings.objects.get_or_create(
        admin=request.user,
        defaults={
            'check_in_time': time(9, 0),
            'check_out_time': time(18, 0),
            'working_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        }
    )
    
    if request.method == 'POST':
        form = AdminAttendanceSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            settings_instance = form.save(commit=False)
            
            # Save working days
            settings_instance.working_days = form.cleaned_data.get('working_days')
            
            # Save custom holidays
            holidays_json = form.cleaned_data.get('custom_holidays_json')
            try:
                settings_instance.custom_holidays = json.loads(holidays_json) if holidays_json else []
            except Exception:
                settings_instance.custom_holidays = []
                
            settings_instance.save()

            # Update shift timings if multiple shifts are present
            from .models import Shift, ShiftTimingLog
            from datetime import datetime
            shifts = Shift.objects.filter(admin=request.user)
            for shift in shifts:
                start_key = f'shift_{shift.id}_start'
                end_key = f'shift_{shift.id}_end'
                if start_key in request.POST and end_key in request.POST:
                    try:
                        new_start = datetime.strptime(request.POST[start_key], "%H:%M").time()
                        new_end = datetime.strptime(request.POST[end_key], "%H:%M").time()
                        
                        if shift.start_time != new_start or shift.end_time != new_end:
                            prev_start = shift.start_time
                            prev_end = shift.end_time
                            shift.start_time = new_start
                            shift.end_time = new_end
                            shift.save()
                            
                            # Log change to ShiftTimingLog
                            ShiftTimingLog.objects.create(
                                admin=request.user,
                                shift=shift,
                                previous_start_time=prev_start,
                                previous_end_time=prev_end,
                                updated_start_time=new_start,
                                updated_end_time=new_end
                            )
                    except Exception as e:
                        pass

            messages.success(request, "Attendance and shift settings updated successfully.")
            return redirect('attendance:attendance_settings')
        else:
            messages.error(request, "Failed to update settings. Please check the values.")
    else:
        # Load initial values
        initial_holidays = json.dumps(settings_obj.custom_holidays)
        form = AdminAttendanceSettingsForm(instance=settings_obj, initial={
            'working_days': settings_obj.working_days,
            'custom_holidays_json': initial_holidays
        })
        
    from .models import Shift
    shifts = Shift.objects.filter(admin=request.user)
    
    return render(request, 'attendance/attendance_settings.html', {
        'form': form,
        'settings': settings_obj,
        'custom_holidays_json': json.dumps(settings_obj.custom_holidays),
        'shifts': shifts,
    })

@login_required
@admin_required
def edit_attendance_record(request, pk):
    """
    Allows admins to manually modify an employee's check-in/out times and status.
    """
    from .forms import AttendanceRecordEditForm
    record = get_object_or_404(AttendanceRecord, pk=pk, user__employeeprofile__created_by=request.user)
    
    if request.method == 'POST':
        form = AttendanceRecordEditForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, f"Attendance record for {record.user.display_username} updated successfully.")
            
            # Write audit logs for this manual edit
            AttendanceLog.objects.create(
                user=record.user,
                action='CHECK_IN',
                status='SUCCESS',
                details=f"Attendance record manually updated by Admin {request.user.username}."
            )
            return redirect('attendance:attendance_logs')
        else:
            messages.error(request, "Failed to save changes. Please review input values.")
    else:
        form = AttendanceRecordEditForm(instance=record)
        
    return render(request, 'attendance/edit_attendance.html', {'form': form, 'record': record})

@login_required
@admin_required
def edit_overtime_record(request, pk):
    """
    Allows admins to manually modify an employee's overtime check-in/out times.
    """
    from .forms import OvertimeRecordEditForm
    record = get_object_or_404(OvertimeRecord, pk=pk, user__employeeprofile__created_by=request.user)
    
    if request.method == 'POST':
        form = OvertimeRecordEditForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, f"Overtime record for {record.user.display_username} updated successfully.")
            
            # Write audit logs for this manual edit
            AttendanceLog.objects.create(
                user=record.user,
                action='CHECK_IN',
                status='SUCCESS',
                details=f"Overtime record manually updated by Admin {request.user.username}."
            )
            return redirect('attendance:attendance_logs')
        else:
            messages.error(request, "Failed to save changes. Please review input values.")
    else:
        form = OvertimeRecordEditForm(instance=record)
        
    return render(request, 'attendance/edit_overtime.html', {'form': form, 'record': record})

@login_required
@admin_required
def shift_list(request):
    """
    Allows admins to view all assigned shift slots and modify their timings.
    """
    from .models import Shift, AdminShiftConfiguration
    shifts = Shift.objects.filter(admin=request.user)
    config_obj, _ = AdminShiftConfiguration.objects.get_or_create(admin=request.user)
    return render(request, 'attendance/shift_list.html', {
        'shifts': shifts,
        'config': config_obj,
    })

@login_required
@admin_required
def shift_edit(request, pk):
    """
    Allows admins to modify timings for their assigned shift slots.
    """
    from .models import Shift, ShiftTimingLog
    from datetime import datetime
    shift = get_object_or_404(Shift, pk=pk, admin=request.user)
    
    if request.method == 'POST':
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        
        try:
            prev_start = shift.start_time
            prev_end = shift.end_time
            
            new_start = datetime.strptime(start_time_str, "%H:%M").time()
            new_end = datetime.strptime(end_time_str, "%H:%M").time()
            
            shift.start_time = new_start
            shift.end_time = new_end
            shift.save()
            
            # Log the timing modification
            ShiftTimingLog.objects.create(
                admin=request.user,
                shift=shift,
                previous_start_time=prev_start,
                previous_end_time=prev_end,
                updated_start_time=new_start,
                updated_end_time=new_end
            )
            
            messages.success(request, f"Shift timings for '{shift.name}' updated successfully.")
        except Exception as e:
            messages.error(request, f"Error updating shift timing: {str(e)}")
            
    return redirect('attendance:shift_list')

@login_required
@admin_required
def shift_timing_logs(request):
    """
    View shift timing modification logs.
    """
    from .models import ShiftTimingLog
    logs = ShiftTimingLog.objects.filter(admin=request.user).select_related('shift').order_by('-modified_at')
    return render(request, 'attendance/shift_timing_logs.html', {'logs': logs})
