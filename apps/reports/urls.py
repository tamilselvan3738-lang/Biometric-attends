from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('attendance/', views.attendance_report_view, name='attendance_report'),
    path('my-report/', views.employee_report_view, name='employee_report'),
    path('analytics/', views.analytics_view, name='analytics'),
]
