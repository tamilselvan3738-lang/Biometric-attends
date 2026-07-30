from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

def home_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboards:dispatcher')
    return redirect('accounts:login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('super-admin/', include('apps.super_admin.urls', namespace='super_admin')),
    path('departments/', include('apps.departments.urls', namespace='departments')),
    path('employees/', include('apps.employee_management.urls', namespace='employee_management')),
    path('biometric/', include('apps.biometric.urls', namespace='biometric')),
    path('attendance/', include('apps.attendance.urls', namespace='attendance')),
    path('leaves/', include('apps.leave_management.urls', namespace='leave_management')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('dashboards/', include('apps.dashboards.urls', namespace='dashboards')),
    path('api/', include('apps.api.urls', namespace='api')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
