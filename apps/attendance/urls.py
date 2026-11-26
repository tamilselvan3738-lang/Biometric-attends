from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('check-in/', views.check_in, name='check_in'),
    path('check-in/api/', views.check_in_api, name='check_in_api'),
    path('check-out/', views.check_out, name='check_out'),
    path('check-out/api/', views.check_out_api, name='check_out_api'),
    path('ot-check-in/', views.ot_check_in, name='ot_check_in'),
    path('ot-check-in/api/', views.ot_check_in_api, name='ot_check_in_api'),
    path('ot-check-out/', views.ot_check_out, name='ot_check_out'),
    path('ot-check-out/api/', views.ot_check_out_api, name='ot_check_out_api'),
    path('history/', views.attendance_history, name='history'),
    path('logs/', views.attendance_logs, name='attendance_logs'),
    path('settings/', views.attendance_settings_view, name='attendance_settings'),
    path('logs/edit/<int:pk>/', views.edit_attendance_record, name='edit_attendance_record'),
    path('ot-logs/edit/<int:pk>/', views.edit_overtime_record, name='edit_overtime_record'),
    path('shifts/', views.shift_list, name='shift_list'),
    path('shifts/edit/<int:pk>/', views.shift_edit, name='shift_edit'),
    path('shifts/logs/', views.shift_timing_logs, name='shift_timing_logs'),
]
