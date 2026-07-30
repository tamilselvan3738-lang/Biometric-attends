from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Notification, Announcement
from apps.accounts.permissions import admin_required

@login_required
def notification_list(request):
    """
    Lists user-specific alerts and announcements based on role permissions.
    """
    # Fetch notifications as a list to retain their unread state for styling on the current page
    user_notifications = list(Notification.objects.filter(recipient=request.user))
    
    # Mark all unread notifications as read in the database
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    
    # Filter announcements by user role
    role_filter = Q(target_role='ALL')
    if request.user.role == 'ADMIN':
        role_filter |= Q(target_role='ADMINS')
    elif request.user.role == 'EMPLOYEE':
        role_filter |= Q(target_role='EMPLOYEES')
        
    announcements = Announcement.objects.filter(role_filter)
    
    return render(request, 'notifications/notifications.html', {
        'notifications': user_notifications,
        'announcements': announcements
    })

@login_required
def mark_as_read(request, pk):
    """
    Marks a user notification as read.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    messages.success(request, "Notification marked as read.")
    return redirect('notifications:list')

@login_required
@admin_required
def create_announcement(request):
    """
    Allows administrators to publish announcements.
    """
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        target = request.POST.get('target_role', 'ALL')
        
        if title and content:
            Announcement.objects.create(
                sender=request.user,
                title=title,
                content=content,
                target_role=target
            )
            messages.success(request, "Global announcement published successfully.")
            return redirect('notifications:list')
        else:
            messages.error(request, "Please fill in all announcement fields.")
            
    return render(request, 'notifications/announcement.html')
