from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('forgot-password/sent/', views.otp_sent_view, name='otp_sent'),
    path('forgot-password/verify/', views.verify_otp_view, name='verify_otp'),
    path('forgot-password/expired/', views.otp_expired_view, name='otp_expired'),
    path('forgot-password/reset/', views.reset_password_view, name='reset_password'),
]
