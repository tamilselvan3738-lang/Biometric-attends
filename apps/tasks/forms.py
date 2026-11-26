from django import forms
from django.contrib.auth import get_user_model
from .models import Task, TaskAssignment, TaskComment

User = get_user_model()

class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True

class TaskCreateForm(forms.ModelForm):
    assigned_employees = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input bg-dark border-secondary'}),
        label="Assign To Employees"
    )
    files = forms.FileField(
        required=False,
        widget=MultipleFileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
        label="Attach Supporting Documents / Images (Optional)"
    )
    
    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'start_date', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'Enter task title'}),
            'description': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 4, 'placeholder': 'Detailed instructions...'}),
            'priority': forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        creator = kwargs.pop('creator', None) or kwargs.pop('manager', None)
        super().__init__(*args, **kwargs)
        if creator:
            enable_employee_types = True
            if creator.role == 'ADMIN':
                admin_user = creator
            else:
                admin_user = creator.employeeprofile.created_by if hasattr(creator, 'employeeprofile') else None
                
            if admin_user:
                try:
                    enable_employee_types = admin_user.organization.enable_employee_types
                except Exception:
                    pass
                    
            if not enable_employee_types:
                self.fields['assigned_employees'].queryset = User.objects.filter(
                    role='EMPLOYEE',
                    is_active=True,
                    employeeprofile__created_by=admin_user,
                    employeeprofile__status='ACTIVE'
                )
            else:
                self.fields['assigned_employees'].queryset = User.objects.filter(
                    role='EMPLOYEE',
                    is_active=True,
                    employeeprofile__reporting_manager=creator,
                    employeeprofile__status='ACTIVE'
                )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        due_date = cleaned_data.get('due_date')
        if start_date and due_date and start_date > due_date:
            self.add_error('due_date', "Due date cannot be before start date.")
        return cleaned_data

class TaskUpdateForm(forms.ModelForm):
    assigned_employees = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input bg-dark border-secondary'}),
        label="Assign To Employees"
    )
    files = forms.FileField(
        required=False,
        widget=MultipleFileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
        label="Attach Additional Files (Optional)"
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'start_date', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'description': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 4}),
            'priority': forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        creator = kwargs.pop('creator', None) or kwargs.pop('manager', None)
        super().__init__(*args, **kwargs)
        if creator:
            enable_employee_types = True
            if creator.role == 'ADMIN':
                admin_user = creator
            else:
                admin_user = creator.employeeprofile.created_by if hasattr(creator, 'employeeprofile') else None
                
            if admin_user:
                try:
                    enable_employee_types = admin_user.organization.enable_employee_types
                except Exception:
                    pass
                    
            if not enable_employee_types:
                self.fields['assigned_employees'].queryset = User.objects.filter(
                    role='EMPLOYEE',
                    is_active=True,
                    employeeprofile__created_by=admin_user,
                    employeeprofile__status='ACTIVE'
                )
            else:
                self.fields['assigned_employees'].queryset = User.objects.filter(
                    role='EMPLOYEE',
                    is_active=True,
                    employeeprofile__reporting_manager=creator,
                    employeeprofile__status='ACTIVE'
                )
                
            if self.instance and self.instance.pk:
                self.fields['assigned_employees'].initial = self.instance.assignments.values_list('employee_id', flat=True)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        due_date = cleaned_data.get('due_date')
        if start_date and due_date and start_date > due_date:
            self.add_error('due_date', "Due date cannot be before start date.")
        return cleaned_data

class EmployeeTaskUpdateForm(forms.ModelForm):
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3, 'placeholder': 'Optional progress details or updates...'}),
        label="Add Comment / Update Description"
    )
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
        label="Upload Supporting File (Optional)"
    )

    class Meta:
        model = TaskAssignment
        fields = ['status']
        widgets = {
            'status': forms.Select(choices=TaskAssignment.STATUS_CHOICES[:4], attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit choices for employee updating status
        self.fields['status'].choices = [
            ('NOT_STARTED', 'Not Started'),
            ('IN_PROGRESS', 'In Progress'),
            ('ON_HOLD', 'On Hold'),
            ('COMPLETED', 'Completed'),
        ]

class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 2, 'placeholder': 'Type your comment...'}),
        }
        labels = {
            'content': '',
        }
