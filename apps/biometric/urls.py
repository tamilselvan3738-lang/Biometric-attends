from django.urls import path
from . import views

app_name = 'biometric'

urlpatterns = [
    path('enroll/', views.enroll_face, name='enroll_face'),
    path('enroll/api/', views.enroll_api, name='enroll_api'),
    path('detect/', views.detect_face_api, name='detect_face_api'),
    path('logs/', views.biometric_logs, name='biometric_logs'),
    path('delete/', views.delete_biometrics, name='delete_biometrics'),
]
