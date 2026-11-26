from django.urls import path
from . import views

app_name = 'employee_management'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    path('inactive/', views.inactive_employees, name='inactive_employees'),
    path('add/', views.add_employee, name='add_employee'),
    path('edit/<int:pk>/', views.edit_employee, name='edit_employee'),
    path('details/<int:pk>/', views.employee_details, name='employee_details'),
    path('api/monthly-attendance/<int:pk>/', views.employee_monthly_attendance_api, name='employee_monthly_attendance_api'),
    path('delete/<int:pk>/', views.delete_employee, name='delete_employee'),
    path('deactivate/<int:pk>/', views.deactivate_employee, name='deactivate_employee'),
    path('activate/<int:pk>/', views.activate_employee, name='activate_employee'),
    path('unlock-biometrics/<int:pk>/', views.unlock_biometrics, name='unlock_biometrics'),
]
