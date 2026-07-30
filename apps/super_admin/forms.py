from django import forms
from django.contrib.auth import get_user_model
from .models import CompanyProfile, SystemSetting

User = get_user_model()

class AdminAddForm(forms.ModelForm):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    phone_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    max_employees = forms.IntegerField(initial=5, min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    shift_structure = forms.ChoiceField(
        choices=(
            ('GENERAL', 'General Shift (Option 1)'),
            ('MORNING_NIGHT', 'Morning and Night Shifts (Option 2)'),
            ('MORNING_EVENING_NIGHT', 'Morning, Evening, and Night Shifts (Option 3)'),
        ),
        initial='GENERAL',
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    
    # Organization fields
    organization_name = forms.CharField(max_length=150, label="Organization Name", widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    logo = forms.ImageField(required=False, label="Organization Logo", widget=forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    gstin = forms.CharField(max_length=15, required=False, label="GSTIN (Optional)", widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'first_name', 'last_name', 'phone_number']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def save(self, commit=True):
        user = User(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            role='ADMIN',
            phone_number=self.cleaned_data.get('phone_number')
        )
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            from apps.super_admin.models import AdminLimit, OrganizationProfile
            AdminLimit.objects.create(admin=user, max_employees=self.cleaned_data['max_employees'])
            OrganizationProfile.objects.create(
                admin=user,
                name=self.cleaned_data['organization_name'],
                logo=self.cleaned_data.get('logo'),
                gstin=self.cleaned_data.get('gstin')
            )
            # Create Shift configuration
            from apps.attendance.models import AdminShiftConfiguration, Shift
            from datetime import time
            
            structure = self.cleaned_data['shift_structure']
            AdminShiftConfiguration.objects.create(admin=user, structure=structure)
            
            if structure == 'GENERAL':
                Shift.objects.create(admin=user, name='General Shift', start_time=time(9, 0), end_time=time(18, 0))
            elif structure == 'MORNING_NIGHT':
                Shift.objects.create(admin=user, name='Morning Shift', start_time=time(6, 0), end_time=time(14, 0))
                Shift.objects.create(admin=user, name='Night Shift', start_time=time(22, 0), end_time=time(6, 0))
            elif structure == 'MORNING_EVENING_NIGHT':
                Shift.objects.create(admin=user, name='Morning Shift', start_time=time(6, 0), end_time=time(14, 0))
                Shift.objects.create(admin=user, name='Evening Shift', start_time=time(14, 0), end_time=time(22, 0))
                Shift.objects.create(admin=user, name='Night Shift', start_time=time(22, 0), end_time=time(6, 0))
        return user

class AdminEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    phone_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    is_approved = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input bg-dark border-secondary'}))
    max_employees = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    shift_structure = forms.ChoiceField(
        choices=(
            ('GENERAL', 'General Shift (Option 1)'),
            ('MORNING_NIGHT', 'Morning and Night Shifts (Option 2)'),
            ('MORNING_EVENING_NIGHT', 'Morning, Evening, and Night Shifts (Option 3)'),
        ),
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    
    # Organization fields
    organization_name = forms.CharField(max_length=150, label="Organization Name", widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    logo = forms.ImageField(required=False, label="Organization Logo", widget=forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    gstin = forms.CharField(max_length=15, required=False, label="GSTIN (Optional)", widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'is_approved']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            from apps.super_admin.models import AdminLimit, OrganizationProfile
            limit_obj, created = AdminLimit.objects.get_or_create(admin=self.instance, defaults={'max_employees': 5})
            self.fields['max_employees'].initial = limit_obj.max_employees
            
            org_obj, created = OrganizationProfile.objects.get_or_create(admin=self.instance, defaults={'name': 'My Organization'})
            self.fields['organization_name'].initial = org_obj.name
            self.fields['logo'].initial = org_obj.logo
            self.fields['gstin'].initial = org_obj.gstin
            
            from apps.attendance.models import AdminShiftConfiguration
            config_obj, created = AdminShiftConfiguration.objects.get_or_create(admin=self.instance, defaults={'structure': 'GENERAL'})
            self.fields['shift_structure'].initial = config_obj.structure

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            from apps.super_admin.models import AdminLimit, OrganizationProfile
            limit_obj, created = AdminLimit.objects.get_or_create(admin=user)
            limit_obj.max_employees = self.cleaned_data['max_employees']
            limit_obj.save()
            
            org_obj, created = OrganizationProfile.objects.get_or_create(admin=user)
            org_obj.name = self.cleaned_data['organization_name']
            if self.cleaned_data.get('logo'):
                org_obj.logo = self.cleaned_data.get('logo')
            org_obj.gstin = self.cleaned_data.get('gstin')
            org_obj.save()
            
            # Update Shift configuration
            from apps.attendance.models import AdminShiftConfiguration, Shift
            from datetime import time
            
            config_obj, created = AdminShiftConfiguration.objects.get_or_create(admin=user)
            old_structure = config_obj.structure
            new_structure = self.cleaned_data['shift_structure']
            
            if old_structure != new_structure or created:
                config_obj.structure = new_structure
                config_obj.save()
                
                # Delete existing shifts not assigned to employees, or deactivate them, and recreate
                existing_shifts = Shift.objects.filter(admin=user)
                for s in existing_shifts:
                    if not s.employees.exists():
                        s.delete()
                    else:
                        s.is_active = False
                        s.save()
                
                # Create new structures
                if new_structure == 'GENERAL':
                    Shift.objects.create(admin=user, name='General Shift', start_time=time(9, 0), end_time=time(18, 0))
                elif new_structure == 'MORNING_NIGHT':
                    Shift.objects.create(admin=user, name='Morning Shift', start_time=time(6, 0), end_time=time(14, 0))
                    Shift.objects.create(admin=user, name='Night Shift', start_time=time(22, 0), end_time=time(6, 0))
                elif new_structure == 'MORNING_EVENING_NIGHT':
                    Shift.objects.create(admin=user, name='Morning Shift', start_time=time(6, 0), end_time=time(14, 0))
                    Shift.objects.create(admin=user, name='Evening Shift', start_time=time(14, 0), end_time=time(22, 0))
                    Shift.objects.create(admin=user, name='Night Shift', start_time=time(22, 0), end_time=time(6, 0))
        return user

class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ['name', 'address', 'website', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'address': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
            'website': forms.URLInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'logo': forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
        }

class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ['key', 'value', 'description']
        widgets = {
            'key': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'readonly': 'readonly'}),
            'value': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'description': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 2, 'readonly': 'readonly'}),
        }
