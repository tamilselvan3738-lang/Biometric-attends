from django.urls import path
from . import views

app_name = 'dashboards'

urlpatterns = [
    path('dispatcher/', views.dispatcher, name='dispatcher'),
    path('super-admin/', views.super_admin_dashboard, name='super_admin_dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('employee/', views.employee_dashboard, name='employee_dashboard'),
]
