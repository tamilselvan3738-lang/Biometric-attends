import logging
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from apps.accounts.models import User

logger = logging.getLogger(__name__)

class AccountStatusMiddleware:
    """
    Middleware that checks the user's active/terminated status on every request.
    If the user has been deactivated or terminated since their last login,
    their session is immediately invalidated, they are logged out, and
    an appropriate termination message is displayed.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                # Fetch fresh status from the database to bypass session caching
                user = User.objects.get(pk=request.user.pk)
                if user.is_terminated or not user.is_active or not user.is_approved:
                    logger.warning(f"Active session invalidated: User '{user.username}' is deactivated or terminated.")
                    
                    # Log out first to clear session
                    logout(request)
                    
                    # Set role-specific error message
                    if user.role == 'ADMIN':
                        messages.error(request, "Your account has been terminated. Please contact the Super Administrator.")
                    else:
                        messages.error(request, "Your account has been terminated. Please contact your administrator for further assistance.")
                        
                    return redirect('accounts:login')
            except User.DoesNotExist:
                # User was permanently deleted
                logger.warning(f"Active session invalidated: User pk {request.user.pk} no longer exists.")
                logout(request)
                messages.error(request, "Your account has been permanently deleted.")
                return redirect('accounts:login')
            except Exception as e:
                logger.error(f"Error in AccountStatusMiddleware: {e}")

        response = self.get_response(request)
        return response
