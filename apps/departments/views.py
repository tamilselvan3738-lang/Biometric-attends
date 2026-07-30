from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Department
from .forms import DepartmentForm
from apps.accounts.permissions import admin_or_super_admin_required

@login_required
def department_list(request):
    departments = Department.objects.all().select_related('manager')
    return render(request, 'departments/department_list.html', {'departments': departments})

@login_required
@admin_or_super_admin_required
def add_department(request):
    form = DepartmentForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Department has been successfully created.")
            return redirect('departments:list')
        else:
            messages.error(request, "Failed to create department. Please resolve form errors.")
            
    return render(request, 'departments/add_department.html', {'form': form})

@login_required
@admin_or_super_admin_required
def edit_department(request, pk):
    department = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=department)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Department has been updated successfully.")
            return redirect('departments:list')
        else:
            messages.error(request, "Failed to update department. Resolve errors.")
            
    return render(request, 'departments/edit_department.html', {'form': form, 'department': department})

@login_required
@admin_or_super_admin_required
def delete_department(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        department.delete()
        messages.success(request, "Department deleted successfully.")
    return redirect('departments:list')
