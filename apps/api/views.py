from rest_framework import viewsets, permissions
from django.contrib.auth import get_user_model
from apps.departments.models import Department
from apps.employee_management.models import EmployeeProfile
from apps.attendance.models import AttendanceRecord
from apps.leave_management.models import LeaveRequest
from .serializers import (
    UserSerializer, DepartmentSerializer, EmployeeProfileSerializer,
    AttendanceRecordSerializer, LeaveRequestSerializer
)
from .permissions import IsSuperAdmin, IsAdmin, IsEmployee, IsAdminOrSuperAdmin

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsSuperAdmin]

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminOrSuperAdmin()]

class EmployeeProfileViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeProfileSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'SUPER_ADMIN']:
            return EmployeeProfile.objects.all()
        return EmployeeProfile.objects.filter(user=user)

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsAdmin()]
        return [permissions.IsAuthenticated()]

class AttendanceRecordViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'SUPER_ADMIN']:
            return AttendanceRecord.objects.all()
        return AttendanceRecord.objects.filter(user=user)

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'SUPER_ADMIN']:
            return LeaveRequest.objects.all()
        return LeaveRequest.objects.filter(user=user)

    def get_permissions(self):
        return [permissions.IsAuthenticated()]
