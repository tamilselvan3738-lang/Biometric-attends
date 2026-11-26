from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'api'

router = DefaultRouter()
router.register('users', views.UserViewSet, basename='user')
router.register('departments', views.DepartmentViewSet, basename='department')
router.register('employees', views.EmployeeProfileViewSet, basename='employee')
router.register('attendance', views.AttendanceRecordViewSet, basename='attendance')
router.register('leaves', views.LeaveRequestViewSet, basename='leave')

urlpatterns = [
    path('', include(router.urls)),
]
