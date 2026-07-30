from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
import json
from .models import FaceEnrollment, BiometricLog
from .face_engine import FaceEngine
from apps.accounts.permissions import admin_required, employee_required, admin_or_super_admin_required

User = get_user_model()

@login_required
@admin_required
def enroll_face(request):
    """
    Renders the face registration template page.
    """
    user_id = request.GET.get('user_id')
    target_user = request.user
    
    if user_id:
        if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            messages.error(request, "Access Denied: You do not have permission to enroll other users.")
            return redirect('dashboards:dispatcher')
        target_user = get_object_or_404(User, pk=user_id, employeeprofile__created_by=request.user)
        
    enrolled = FaceEnrollment.objects.filter(user=target_user).exists()
    return render(request, 'biometric/enroll_face.html', {'enrolled': enrolled, 'target_user': target_user})

@login_required
@admin_required
def enroll_api(request):
    """
    API endpoint that receives single or multiple base64 webcam frames and registers a face profile.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})
        
    try:
        data = json.loads(request.body)
        base64_image = data.get('image')
        base64_images = data.get('images') # list of images
        user_id = data.get('user_id')
        
        target_user = request.user
        if user_id:
            if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
                return JsonResponse({'success': False, 'message': 'Access Denied: Permission required to enroll other users.'})
            target_user = get_object_or_404(User, pk=user_id, employeeprofile__created_by=request.user)
            
        engine = FaceEngine()
        face_templates = []
        scores = []
        first_img_bytes = None
        first_analysis = {}
        
        if base64_images:
            for idx, b64 in enumerate(base64_images):
                success, face_list, img_bytes, message, q_score, checks, facial_analysis = engine.register_face(b64)
                if not success:
                    BiometricLog.objects.create(
                        user=target_user,
                        action='ENROLL',
                        status='FAILURE',
                        details=f"Pose {idx+1} failed quality check: {message} (Action by {request.user.username})"
                    )
                    return JsonResponse({'success': False, 'message': f"Pose {idx+1} failed quality check: {message}"})
                face_templates.append(face_list)
                scores.append(q_score)
                if idx == 0:
                    first_img_bytes = img_bytes
                    first_analysis = facial_analysis
        elif base64_image:
            success, face_list, img_bytes, message, q_score, checks, facial_analysis = engine.register_face(base64_image)
            if not success:
                BiometricLog.objects.create(
                    user=target_user,
                    action='ENROLL',
                    status='FAILURE',
                    details=f"{message} (Action by {request.user.username})"
                )
                return JsonResponse({'success': False, 'message': message})
            face_templates.append(face_list)
            scores.append(q_score)
            first_img_bytes = img_bytes
            first_analysis = facial_analysis
        else:
            return JsonResponse({'success': False, 'message': 'No image data provided.'})
            
        if len(face_templates) == 0:
            return JsonResponse({'success': False, 'message': 'No valid face profiles captured.'})
            
        # Calculate average quality score
        avg_score = sum(scores) / len(scores)
        if avg_score < 70:
            return JsonResponse({'success': False, 'message': f"Enrollment rejected: Quality score too low ({avg_score:.1f} < 70). Please ensure good lighting and position."})

        # Anti-Spoofing: Check if the user is holding a static photo
        if len(face_templates) > 1:
            sims_to_first = [engine.compute_similarity(face_templates[0], t) for t in face_templates[1:]]
            if len(sims_to_first) > 0:
                min_sim = min(sims_to_first)
                # If similarity is nearly identical across all poses, no real head movement occurred
                if min_sim > 0.97:
                    BiometricLog.objects.create(
                        user=target_user,
                        action='ENROLL',
                        status='FAILURE',
                        details=f"Static photo registration blocked. No head movement detected. (Action by {request.user.username})"
                    )
                    return JsonResponse({
                        'success': False,
                        'message': 'Liveness Verification Failed: No head movement detected (static photo blocked).'
                    })
            
        # Save face data and thumbnail
        enrollment, created = FaceEnrollment.objects.get_or_create(user=target_user)
        
        # Store as advanced dictionary mapping
        enrollment_dict = {
            "templates": face_templates,
            "quality_score": avg_score,
            "timestamp": timezone.now().isoformat(),
            "facial_analysis": first_analysis
        }
        enrollment.face_data = json.dumps(enrollment_dict)
        
        # Save the raw cropped face image to media storage (using front-facing sample)
        file_name = f"user_{target_user.id}_face.jpg"
        enrollment.enrolled_image.save(file_name, ContentFile(first_img_bytes), save=False)
        enrollment.save()
        
        # Auditing Log
        BiometricLog.objects.create(
            user=target_user,
            action='ENROLL',
            status='SUCCESS',
            details=f"Face profile successfully captured and enrolled with {len(face_templates)} samples. Quality Score: {avg_score:.1f}. (Action by {request.user.username})"
        )
        return JsonResponse({'success': True, 'message': 'Face enrollment successful!'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Server Exception: {str(e)}"})

@login_required
@admin_required
def detect_face_api(request):
    """
    API endpoint to check if a face can be successfully detected in a base64 image frame,
    running full quality validation checks (size, brightness, blur, and eye visibility).
    Returns success status without updating database records.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})
        
    try:
        data = json.loads(request.body)
        base64_image = data.get('image')
        if not base64_image:
            return JsonResponse({'success': False, 'message': 'No image data provided.'})
            
        engine = FaceEngine()
        img = engine.decode_base64_image(base64_image)
        face_normalized, bbox = engine.extract_face(img)
        
        if face_normalized is None or bbox is None:
            return JsonResponse({'success': False, 'message': 'No face detected in the frame. Position yourself directly in front of the camera.'})
            
        # Run full quality check
        quality_ok, quality_msg, quality_score, checks = engine.validate_face_quality(img, face_normalized, bbox)
        facial_analysis = engine.analyze_facial_features(face_normalized, bbox)
        if not quality_ok:
            return JsonResponse({
                'success': False,
                'message': quality_msg,
                'quality_score': quality_score,
                'checks': checks,
                'facial_analysis': facial_analysis
            })
            
        return JsonResponse({
            'success': True,
            'message': 'Face detected and quality validation passed!',
            'quality_score': quality_score,
            'checks': checks,
            'facial_analysis': facial_analysis,
            'bbox': {
                'x': int(bbox[0]),
                'y': int(bbox[1]),
                'w': int(bbox[2]),
                'h': int(bbox[3])
            }
        })
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Detection system error: {str(e)}"})

@login_required
@admin_required
def biometric_logs(request):
    """
    Allows admins to audit face enrollment and verification attempts. Isolated by creator.
    """
    logs = BiometricLog.objects.filter(user__employeeprofile__created_by=request.user).select_related('user')
    return render(request, 'biometric/biometric_logs.html', {'logs': logs})

@login_required
@admin_required
def delete_biometrics(request):
    """
    Deletes the target user's biometric template.
    """
    user_id = None
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        target_user = request.user
        
        if user_id:
            if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
                messages.error(request, "Access Denied: You do not have permission to delete other users' templates.")
                return redirect('dashboards:dispatcher')
            target_user = get_object_or_404(User, pk=user_id, employeeprofile__created_by=request.user)
            
        enrollment = FaceEnrollment.objects.filter(user=target_user)
        if enrollment.exists():
            enrollment.delete()
            BiometricLog.objects.create(
                user=target_user,
                action='DELETE',
                status='SUCCESS',
                details=f"User's biometric templates cleared. (Action by {request.user.username})"
            )
            messages.success(request, f"Face biometric templates for {target_user.username} have been deleted.")
        else:
            messages.error(request, f"No face biometric templates found to delete for {target_user.username}.")
            
    if user_id:
        return redirect(f"/biometric/enroll/?user_id={user_id}")
    return redirect('biometric:enroll_face')
