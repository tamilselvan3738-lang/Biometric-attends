from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def role_required(allowed_roles):
    """
    Decorator for views that checks if the logged-in user has the required role.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "Access Denied: You do not have permission to view this page.")
                return redirect('dashboards:dispatcher')
        return _wrapped_view
    return decorator

# Specific role decorators
def super_admin_required(view_func):
    return role_required(['SUPER_ADMIN'])(view_func)

def admin_required(view_func):
    return role_required(['ADMIN'])(view_func)

def employee_required(view_func):
    return role_required(['EMPLOYEE'])(view_func)

def admin_or_super_admin_required(view_func):
    return role_required(['ADMIN', 'SUPER_ADMIN'])(view_func)


# Class-based view mixins
class SuperAdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'SUPER_ADMIN'
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Access Denied: Super Admin permission required.")
            return redirect('dashboards:dispatcher')
        return redirect('accounts:login')

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'ADMIN'
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Access Denied: Admin permission required.")
            return redirect('dashboards:dispatcher')
        return redirect('accounts:login')

class EmployeeRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'EMPLOYEE'
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Access Denied: Employee permission required.")
            return redirect('dashboards:dispatcher')
        return redirect('accounts:login')

class AdminOrSuperAdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role in ['ADMIN', 'SUPER_ADMIN']
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Access Denied: Admin/Super Admin permission required.")
            return redirect('dashboards:dispatcher')
        return redirect('accounts:login')
