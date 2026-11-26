from django import forms
from .models import Department
from django.contrib.auth import get_user_model

User = get_user_model()

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'manager']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'code': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'description': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
            'manager': forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only list SUPER_ADMIN and ADMIN users as eligible managers
        self.fields['manager'].queryset = User.objects.filter(role__in=['SUPER_ADMIN', 'ADMIN'])
