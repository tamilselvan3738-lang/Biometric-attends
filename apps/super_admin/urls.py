from django.urls import path
from . import views

app_name = 'super_admin'

urlpatterns = [
    path('admins/', views.admin_list, name='admin_list'),
    path('admins/create/', views.create_admin, name='create_admin'),
    path('admins/edit/<int:pk>/', views.edit_admin, name='edit_admin'),
    path('admins/delete/<int:pk>/', views.delete_admin, name='delete_admin'),
    path('admins/deactivate/<int:pk>/', views.deactivate_admin, name='deactivate_admin'),
    path('admins/activate/<int:pk>/', views.activate_admin, name='activate_admin'),
    path('company/', views.company_profile_view, name='company_list'),
    path('settings/', views.settings_view, name='settings'),
    path('limit-requests/', views.review_limit_requests, name='review_limit_requests'),
    path('limit-requests/approve/<int:pk>/', views.approve_limit_request, name='approve_limit_request'),
    path('limit-requests/reject/<int:pk>/', views.reject_limit_request, name='reject_limit_request'),
    path('limit-requests/request/', views.request_limit_increase, name='request_limit_increase'),
    
    # Shift management routes for Super Admin
    path('admins/<int:admin_id>/shifts/', views.super_admin_shift_list, name='super_admin_shift_list'),
    path('admins/<int:admin_id>/shifts/create/', views.super_admin_shift_create, name='super_admin_shift_create'),
    path('admins/<int:admin_id>/shifts/edit/<int:pk>/', views.super_admin_shift_edit, name='super_admin_shift_edit'),
    path('admins/<int:admin_id>/shifts/delete/<int:pk>/', views.super_admin_shift_delete, name='super_admin_shift_delete'),
    path('admins/<int:admin_id>/shifts/toggle/<int:pk>/', views.super_admin_shift_toggle, name='super_admin_shift_toggle'),
]
