from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Manager Views
    path('manager/', views.manager_task_list, name='manager_task_list'),
    path('manager/create/', views.manager_task_create, name='manager_task_create'),
    path('manager/edit/<int:pk>/', views.manager_task_update, name='manager_task_update'),
    path('manager/cancel/<int:pk>/', views.manager_task_cancel, name='manager_task_cancel'),
    path('manager/detail/<int:pk>/', views.manager_task_detail, name='manager_task_detail'),
    path('manager/export/excel/', views.export_tasks_excel, name='export_tasks_excel'),
    path('manager/export/pdf/', views.export_tasks_pdf, name='export_tasks_pdf'),
    
    # Employee Views
    path('employee/', views.employee_task_list, name='employee_task_list'),
    path('employee/detail/<int:pk>/', views.employee_task_detail, name='employee_task_detail'),
]
