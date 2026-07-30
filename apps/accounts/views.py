from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm, UserProfileForm
from .models import User

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboards:dispatcher')
        
    form = LoginForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            if '/' in username:
                username = username.replace('/', '_')
                
            # Check if this username is in the TerminatedAccount table
            from apps.super_admin.models import TerminatedAccount
            import logging
            logger = logging.getLogger(__name__)
            
            terminated = TerminatedAccount.objects.filter(username=username).exists()
            if not terminated and '_' not in username:
                terminated = TerminatedAccount.objects.filter(username__endswith=f"_{username}", role='EMPLOYEE').exists()
                
            if terminated:
                db_user = User.objects.filter(username=username).first()
                if not db_user and '_' not in username:
                    db_user = User.objects.filter(username__endswith=f"_{username}", role='EMPLOYEE').first()
                logger.warning(f"Blocked login attempt from terminated username: {username}")
                if db_user and db_user.role == 'ADMIN':
                    messages.error(request, "Your account has been terminated. Please contact the Super Administrator.")
                else:
                    messages.error(request, "Your account has been terminated. Please contact your administrator for further assistance.")
                return render(request, 'accounts/login.html', {'form': form, 'no_layout': True})
                
            # Check if this user is marked inactive (is_approved=False or is_active=False or is_terminated=True)
            try:
                db_user = User.objects.filter(username=username).first()
                if not db_user and '_' not in username:
                    db_user = User.objects.filter(username__endswith=f"_{username}", role='EMPLOYEE').first()
                    
                if db_user and (not db_user.is_approved or not db_user.is_active or db_user.is_terminated):
                    logger.warning(f"Blocked login attempt from inactive/terminated user: {username}")
                    if db_user.role == 'ADMIN':
                        messages.error(request, "Your account has been terminated. Please contact the Super Administrator.")
                    else:
                        messages.error(request, "Your account has been terminated. Please contact your administrator for further assistance.")
                    return render(request, 'accounts/login.html', {'form': form, 'no_layout': True})
            except Exception:
                pass

            user = authenticate(request, username=username, password=password)
            
            # If not authenticated, check if this is an employee user with a prefixed username
            if user is None and '_' not in username:
                matching_users = User.objects.filter(username__endswith=f"_{username}", role='EMPLOYEE')
                for possible_user in matching_users:
                    authenticated_user = authenticate(request, username=possible_user.username, password=password)
                    if authenticated_user is not None:
                        user = authenticated_user
                        break
            
            if user is not None:
                if user.is_approved and user.is_active and not user.is_terminated:
                    login(request, user)
                    messages.success(request, f"Welcome back, {user.first_name or user.display_username}!")
                    return redirect('dashboards:dispatcher')
                else:
                    logger.warning(f"Blocked login attempt from authenticated inactive/terminated user: {user.username}")
                    if user.role == 'ADMIN':
                        messages.error(request, "Your account has been terminated. Please contact the Super Administrator.")
                    else:
                        messages.error(request, "Your account has been terminated. Please contact your administrator for further assistance.")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid form submissions.")
            
    return render(request, 'accounts/login.html', {'form': form, 'no_layout': True})

def logout_view(request):
    logout(request)
    messages.success(request, "You have successfully logged out.")
    return redirect('accounts:login')

@login_required
def profile_view(request):
    profile = request.user.userprofile
    form = UserProfileForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please correct the errors below.")
            
    return render(request, 'accounts/profile.html', {'form': form})

@login_required
def change_password_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep session active
            messages.success(request, "Your password was successfully updated!")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please correct the password errors below.")
            
    return render(request, 'accounts/change_password.html', {'form': form})

import logging
import random
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import ForgotPasswordOTP

logger = logging.getLogger(__name__)

def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('dashboards:dispatcher')

    if request.GET.get('restart') == 'true':
        request.session.pop('reset_username', None)
        request.session.pop('otp_record_id', None)
        return redirect('accounts:forgot_password')

    reset_username = request.session.get('reset_username')
    step = 2 if reset_username else 1

    if request.method == 'POST':
        if step == 1:
            username = request.POST.get('username')
            # Check username exists
            if not User.objects.filter(username=username).exists():
                messages.error(request, "Username not found.")
                return render(request, 'accounts/forgot_password.html', {'step': 1, 'no_layout': True})
            
            request.session['reset_username'] = username
            return redirect('accounts:forgot_password')
            
        elif step == 2:
            email = request.POST.get('email')
            user = get_object_or_404(User, username=reset_username)
            
            # Verify email matches username
            if user.email != email:
                messages.error(request, "The email address does not match the selected username.")
                return render(request, 'accounts/forgot_password.html', {'step': 2, 'reset_username': reset_username, 'no_layout': True})
            
            # Generate secure random 6-digit OTP
            otp = str(random.SystemRandom().randint(100000, 999999))
            expires_at = timezone.now() + timedelta(minutes=5)
            
            # Save OTP to database
            otp_record = ForgotPasswordOTP.objects.create(
                user=user,
                username=user.username,
                email=email,
                otp_code=otp,
                expires_at=expires_at,
                is_verified=False,
                is_used=False
            )
            
            # Send Email
            subject = "Password Reset OTP"
            message = f"""Hello {user.username},

We received a password reset request for your account.

Your One-Time Password (OTP) is:

{otp}

This OTP is valid for 5 minutes.

If you did not request a password reset, please ignore this email.

Thank you,
Biometric Attendance System Team"""
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                logger.info(f"Password reset OTP sent to {email} for username: {user.username}")
            except Exception as e:
                logger.error(f"Failed to send password reset OTP: {e}")
            
            request.session['otp_record_id'] = otp_record.id
            return redirect('accounts:otp_sent')

    return render(request, 'accounts/forgot_password.html', {
        'step': step,
        'reset_username': reset_username,
        'no_layout': True
    })

def otp_sent_view(request):
    if request.user.is_authenticated:
        return redirect('dashboards:dispatcher')
    
    otp_record_id = request.session.get('otp_record_id')
    if not otp_record_id:
        return redirect('accounts:forgot_password')
        
    return render(request, 'accounts/otp_sent.html', {'no_layout': True})

def verify_otp_view(request):
    if request.user.is_authenticated:
        return redirect('dashboards:dispatcher')
        
    otp_record_id = request.session.get('otp_record_id')
    if not otp_record_id:
        return redirect('accounts:forgot_password')
        
    otp_record = get_object_or_404(ForgotPasswordOTP, id=otp_record_id)
    
    # Check if expired
    if timezone.now() > otp_record.expires_at:
        return redirect('accounts:otp_expired')
        
    if request.method == 'POST':
        entered_otp = request.POST.get('otp_code', '').strip()
        
        if otp_record.otp_code != entered_otp:
            messages.error(request, "Invalid OTP.")
            return render(request, 'accounts/verify_otp.html', {'no_layout': True})
            
        otp_record.is_verified = True
        otp_record.save()
        return redirect('accounts:reset_password')
        
    return render(request, 'accounts/verify_otp.html', {'no_layout': True})

def otp_expired_view(request):
    if request.user.is_authenticated:
        return redirect('dashboards:dispatcher')
        
    messages.error(request, "OTP has expired. Please request a new OTP.")
    return render(request, 'accounts/otp_expired.html', {'no_layout': True})

def reset_password_view(request):
    if request.user.is_authenticated:
        return redirect('dashboards:dispatcher')
        
    otp_record_id = request.session.get('otp_record_id')
    if not otp_record_id:
        return redirect('accounts:forgot_password')
        
    otp_record = get_object_or_404(ForgotPasswordOTP, id=otp_record_id)
    
    if not otp_record.is_verified or otp_record.is_used:
        messages.error(request, "Invalid access or OTP already used.")
        return redirect('accounts:forgot_password')
        
    if timezone.now() > otp_record.expires_at:
        return redirect('accounts:otp_expired')
        
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/reset_password.html', {'no_layout': True})
            
        try:
            validate_password(password, user=otp_record.user)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return render(request, 'accounts/reset_password.html', {'no_layout': True})
            
        # Update password securely
        otp_record.user.set_password(password)
        otp_record.user.save()
        
        # Invalidate OTP
        otp_record.is_used = True
        otp_record.save()
        
        # Log activity
        logger.info(f"Password reset successful for user: {otp_record.username}")
        
        # Clear session
        request.session.pop('reset_username', None)
        request.session.pop('otp_record_id', None)
        
        messages.success(request, "Password reset successful. Please login with your new password.")
        return redirect('accounts:login')
        
    return render(request, 'accounts/reset_password.html', {'no_layout': True})
