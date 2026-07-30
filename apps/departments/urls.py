from django.urls import path
from . import views

app_name = 'departments'

urlpatterns = [
    path('', views.department_list, name='list'),
    path('add/', views.add_department, name='add'),
    path('edit/<int:pk>/', views.edit_department, name='edit'),
    path('delete/<int:pk>/', views.delete_department, name='delete'),
]
