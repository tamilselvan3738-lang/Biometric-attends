from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('read/<int:pk>/', views.mark_as_read, name='mark_as_read'),
    path('announcement/create/', views.create_announcement, name='create_announcement'),
]
