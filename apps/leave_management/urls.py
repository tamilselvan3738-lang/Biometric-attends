from django.urls import path
from . import views

app_name = 'leave_management'

urlpatterns = [
    path('apply/', views.apply_leave, name='apply_leave'),
    path('history/', views.leave_history, name='leave_history'),
    path('requests/', views.leave_requests, name='leave_requests'),
    path('approve/<int:pk>/', views.approve_leave, name='approve_leave'),
    path('reject/<int:pk>/', views.reject_leave, name='reject_leave'),
    path('details/<int:pk>/', views.leave_details, name='leave_details'),
]
