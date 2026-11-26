from django import forms
from django.contrib.auth import get_user_model
from .models import EmployeeProfile
from apps.departments.models import Department

User = get_user_model()

class EmployeeAddForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-dark text-light border-secondary',
            'autocomplete': 'new-username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control bg-dark text-light border-secondary',
            'autocomplete': 'new-password'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control bg-dark text-light border-secondary',
            'autocomplete': 'off'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-dark text-light border-secondary',
            'autocomplete': 'off'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-dark text-light border-secondary',
            'autocomplete': 'off'
        })
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-dark text-light border-secondary',
            'autocomplete': 'off'
        })
    )
    gender = forms.ChoiceField(
        choices=User.GENDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'})
    )
    current_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 2, 'autocomplete': 'off'})
    )
    permanent_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 2, 'autocomplete': 'off'})
    )
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'autocomplete': 'off'})
    )
    state = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'autocomplete': 'off'})
    )
    country = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'autocomplete': 'off'})
    )
    pincode = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'autocomplete': 'off'})
    )
    nationality = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'autocomplete': 'off'})
    )

    # Profile fields
    employee_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-dark text-light border-secondary',
            'autocomplete': 'off'
        })
    )
    employee_type = forms.ChoiceField(
        choices=EmployeeProfile.EMPLOYEE_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        label="Employee Type"
    )
    reporting_manager = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        label="Reporting Manager"
    )
    need_ot_check_in = forms.ChoiceField(
        choices=(('Yes', 'Yes'), ('No', 'No')),
        initial='Yes',
        required=False,
        label="Need OT Check-In",
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=True, widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}))
    designation = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    date_of_joining = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'}))
    status = forms.ChoiceField(choices=EmployeeProfile.STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}))
    document = forms.FileField(required=False, widget=forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    profile_image = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    shift = forms.ModelChoiceField(
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    custom_check_in_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'time'})
    )
    custom_check_out_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'time'})
    )

    class Meta:
        model = EmployeeProfile
        fields = ['employee_id', 'employee_type', 'reporting_manager', 'department', 'designation', 'date_of_joining', 'status', 'document', 'profile_image', 'shift', 'custom_check_in_time', 'custom_check_out_time']

    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator', None)
        super().__init__(*args, **kwargs)
        from apps.attendance.models import Shift
        
        admin_user = None
        if self.creator:
            if self.creator.role == 'ADMIN':
                admin_user = self.creator
            else:
                try:
                    admin_user = self.creator.employeeprofile.created_by
                except Exception:
                    pass

        if admin_user:
            self.fields['shift'].queryset = Shift.objects.filter(admin=admin_user, is_active=True)
            self.fields['reporting_manager'].queryset = User.objects.filter(
                role='EMPLOYEE',
                is_active=True,
                employeeprofile__employee_type='MANAGER',
                employeeprofile__status='ACTIVE',
                employeeprofile__created_by=admin_user
            )
        else:
            self.fields['shift'].queryset = Shift.objects.filter(is_active=True)
            self.fields['reporting_manager'].queryset = User.objects.filter(
                role='EMPLOYEE',
                is_active=True,
                employeeprofile__employee_type='MANAGER',
                employeeprofile__status='ACTIVE'
            )
        self.fields['employee_type'].required = False
        self.fields['reporting_manager'].required = False

        enable_employee_types = True
        enable_ot = True
        if admin_user:
            try:
                enable_employee_types = admin_user.organization.enable_employee_types
                enable_ot = admin_user.organization.enable_overtime
            except Exception:
                pass

        if not enable_employee_types:
            self.fields['employee_type'].widget = forms.HiddenInput()
            self.fields['employee_type'].initial = 'EMPLOYEE'
            self.fields['reporting_manager'].widget = forms.HiddenInput()
            self.fields['reporting_manager'].initial = None
            self.fields['reporting_manager'].required = False
            
        if not enable_ot or not enable_employee_types:
            self.fields['need_ot_check_in'].widget = forms.HiddenInput()
            self.fields['need_ot_check_in'].initial = 'No'
            self.fields['need_ot_check_in'].required = False

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if self.creator:
            scoped_username = f"{self.creator.username}_{username}"
        else:
            scoped_username = username
        if User.objects.filter(username=scoped_username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean_employee_id(self):
        emp_id = self.cleaned_data.get('employee_id')
        if self.creator:
            scoped_emp_id = f"{self.creator.username}_{emp_id}"
        else:
            scoped_emp_id = emp_id
        if EmployeeProfile.objects.filter(employee_id=scoped_emp_id).exists():
            raise forms.ValidationError("Employee ID already exists.")
        return emp_id

    def clean_employee_type(self):
        if 'employee_type' not in self.data:
            return 'EMPLOYEE'
        val = self.cleaned_data.get('employee_type')
        if not val:
            return 'EMPLOYEE'
        return val

    def clean_reporting_manager(self):
        if 'reporting_manager' not in self.data:
            return None
        val = self.cleaned_data.get('reporting_manager')
        return val

    def clean(self):
        cleaned_data = super().clean()
        
        # Check if employee types are disabled
        admin_user = None
        if self.creator:
            if self.creator.role == 'ADMIN':
                admin_user = self.creator
            else:
                try:
                    admin_user = self.creator.employeeprofile.created_by
                except Exception:
                    pass
        
        enable_employee_types = True
        if admin_user:
            try:
                enable_employee_types = admin_user.organization.enable_employee_types
            except Exception:
                pass
                
        if not enable_employee_types:
            cleaned_data['employee_type'] = 'EMPLOYEE'
            cleaned_data['reporting_manager'] = None
            cleaned_data['need_ot_check_in'] = 'Yes'
            return cleaned_data
            
        employee_type = cleaned_data.get('employee_type')
        reporting_manager = cleaned_data.get('reporting_manager')
        
        if 'employee_type' in self.data or 'reporting_manager' in self.data:
            if employee_type == 'EMPLOYEE':
                if not reporting_manager:
                    self.add_error('reporting_manager', "Reporting Manager is mandatory when Employee Type is Employee.")
            else:
                if reporting_manager:
                    cleaned_data['reporting_manager'] = None
                    
        # Check Need OT Check-In field validation
        try:
            enable_ot = admin_user.organization.enable_overtime
        except Exception:
            enable_ot = True
            
        if enable_ot and employee_type in ['HR_TEAM', 'MANAGER']:
            need_ot_check_in = cleaned_data.get('need_ot_check_in')
            if not need_ot_check_in:
                self.add_error('need_ot_check_in', "This field is mandatory for HR Team and Manager accounts.")
                
        return cleaned_data

    def save(self, commit=True):
        admin_user = None
        if self.creator:
            if self.creator.role == 'ADMIN':
                admin_user = self.creator
            else:
                try:
                    admin_user = self.creator.employeeprofile.created_by
                except Exception:
                    pass

        enable_employee_types = True
        if admin_user:
            try:
                enable_employee_types = admin_user.organization.enable_employee_types
            except Exception:
                pass

        if self.creator:
            scoped_username = f"{self.creator.username}_{self.cleaned_data['username']}"
            scoped_emp_id = f"{self.creator.username}_{self.cleaned_data['employee_id']}"
        else:
            scoped_username = self.cleaned_data['username']
            scoped_emp_id = self.cleaned_data['employee_id']
            
        # Create User
        user = User.objects.create_user(
            username=scoped_username,
            password=self.cleaned_data['password'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            role='EMPLOYEE',
            phone_number=self.cleaned_data.get('phone_number'),
            gender=self.cleaned_data.get('gender'),
            date_of_birth=self.cleaned_data.get('date_of_birth'),
            current_address=self.cleaned_data.get('current_address'),
            permanent_address=self.cleaned_data.get('permanent_address'),
            city=self.cleaned_data.get('city'),
            state=self.cleaned_data.get('state'),
            country=self.cleaned_data.get('country'),
            pincode=self.cleaned_data.get('pincode'),
            nationality=self.cleaned_data.get('nationality')
        )
        # Create Profile
        profile = EmployeeProfile(
            user=user,
            employee_id=scoped_emp_id,
            employee_type=self.cleaned_data['employee_type'],
            reporting_manager=self.cleaned_data.get('reporting_manager'),
            department=self.cleaned_data['department'],
            designation=self.cleaned_data['designation'],
            date_of_joining=self.cleaned_data['date_of_joining'],
            status=self.cleaned_data['status'],
            document=self.cleaned_data.get('document'),
            profile_image=self.cleaned_data.get('profile_image'),
            created_by=self.creator,
            shift=self.cleaned_data['shift'],
            custom_check_in_time=self.cleaned_data.get('custom_check_in_time'),
            custom_check_out_time=self.cleaned_data.get('custom_check_out_time')
        )
        
        # Resolve need_ot_check_in
        enable_ot = True
        if admin_user:
            try:
                enable_ot = admin_user.organization.enable_overtime
            except Exception:
                pass
                
        if not enable_ot:
            profile.need_ot_check_in = False
        elif not enable_employee_types:
            profile.need_ot_check_in = True
        else:
            emp_type = self.cleaned_data.get('employee_type', 'EMPLOYEE')
            if emp_type == 'EMPLOYEE':
                profile.need_ot_check_in = True
            else:
                profile.need_ot_check_in = (self.cleaned_data.get('need_ot_check_in', 'Yes') == 'Yes')
                
        if commit:
            profile.save()
        return profile

class EmployeeEditForm(forms.ModelForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    phone_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    gender = forms.ChoiceField(
        choices=User.GENDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'})
    )
    current_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 2})
    )
    permanent_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 2})
    )
    city = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    state = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    country = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    pincode = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    nationality = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    
    employee_type = forms.ChoiceField(
        choices=EmployeeProfile.EMPLOYEE_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        label="Employee Type"
    )
    reporting_manager = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        label="Reporting Manager"
    )
    need_ot_check_in = forms.ChoiceField(
        choices=(('Yes', 'Yes'), ('No', 'No')),
        initial='Yes',
        required=False,
        label="Need OT Check-In",
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    
    # Profile fields
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=True, widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}))
    designation = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    date_of_joining = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'}))
    status = forms.ChoiceField(choices=EmployeeProfile.STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}))
    document = forms.FileField(required=False, widget=forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    profile_image = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    shift = forms.ModelChoiceField(
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    custom_check_in_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'time'})
    )
    custom_check_out_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'time'})
    )

    class Meta:
        model = EmployeeProfile
        fields = ['employee_type', 'reporting_manager', 'department', 'designation', 'date_of_joining', 'status', 'document', 'profile_image', 'shift', 'custom_check_in_time', 'custom_check_out_time']

    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator', None)
        super().__init__(*args, **kwargs)
        from apps.attendance.models import Shift
        
        admin_user = None
        if self.instance and self.instance.created_by:
            admin_user = self.instance.created_by
            
        if admin_user:
            self.fields['shift'].queryset = Shift.objects.filter(admin=admin_user, is_active=True)
            self.fields['reporting_manager'].queryset = User.objects.filter(
                role='EMPLOYEE',
                is_active=True,
                employeeprofile__employee_type='MANAGER',
                employeeprofile__status='ACTIVE',
                employeeprofile__created_by=admin_user
            )
        else:
            self.fields['shift'].queryset = Shift.objects.filter(is_active=True)
            self.fields['reporting_manager'].queryset = User.objects.filter(
                role='EMPLOYEE',
                is_active=True,
                employeeprofile__employee_type='MANAGER',
                employeeprofile__status='ACTIVE'
            )
        self.fields['employee_type'].required = False
        self.fields['reporting_manager'].required = False

        enable_employee_types = True
        enable_ot = True
        if admin_user:
            try:
                enable_employee_types = admin_user.organization.enable_employee_types
                enable_ot = admin_user.organization.enable_overtime
            except Exception:
                pass

        if not enable_employee_types:
            self.fields['employee_type'].widget = forms.HiddenInput()
            self.fields['employee_type'].initial = 'EMPLOYEE'
            self.fields['reporting_manager'].widget = forms.HiddenInput()
            self.fields['reporting_manager'].initial = None
            self.fields['reporting_manager'].required = False
            
        if not enable_ot or not enable_employee_types:
            self.fields['need_ot_check_in'].widget = forms.HiddenInput()
            self.fields['need_ot_check_in'].initial = 'No'
            self.fields['need_ot_check_in'].required = False
        else:
            if self.instance and self.instance.pk:
                self.fields['need_ot_check_in'].initial = 'Yes' if self.instance.need_ot_check_in else 'No'
            
        if self.instance:
            if self.instance.custom_check_in_time:
                self.fields['custom_check_in_time'].initial = self.instance.custom_check_in_time.strftime('%H:%M')
            if self.instance.custom_check_out_time:
                self.fields['custom_check_out_time'].initial = self.instance.custom_check_out_time.strftime('%H:%M')
            
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['phone_number'].initial = self.instance.user.phone_number
            self.fields['gender'].initial = self.instance.user.gender
            self.fields['date_of_birth'].initial = self.instance.user.date_of_birth
            self.fields['current_address'].initial = self.instance.user.current_address
            self.fields['permanent_address'].initial = self.instance.user.permanent_address
            self.fields['city'].initial = self.instance.user.city
            self.fields['state'].initial = self.instance.user.state
            self.fields['country'].initial = self.instance.user.country
            self.fields['pincode'].initial = self.instance.user.pincode
            self.fields['nationality'].initial = self.instance.user.nationality

    def clean_employee_type(self):
        if 'employee_type' not in self.data:
            if self.instance and self.instance.pk:
                return self.instance.employee_type
            return 'EMPLOYEE'
        val = self.cleaned_data.get('employee_type')
        if not val:
            if self.instance and self.instance.pk:
                return self.instance.employee_type
            return 'EMPLOYEE'
        return val

    def clean_reporting_manager(self):
        if 'reporting_manager' not in self.data:
            if self.instance and self.instance.pk:
                return self.instance.reporting_manager
            return None
        val = self.cleaned_data.get('reporting_manager')
        return val

    def clean(self):
        cleaned_data = super().clean()
        
        # Check if employee types are disabled
        admin_user = None
        if self.instance and self.instance.created_by:
            admin_user = self.instance.created_by
            
        enable_employee_types = True
        if admin_user:
            try:
                enable_employee_types = admin_user.organization.enable_employee_types
            except Exception:
                pass
                
        if not enable_employee_types:
            cleaned_data['employee_type'] = 'EMPLOYEE'
            cleaned_data['reporting_manager'] = None
            cleaned_data['need_ot_check_in'] = 'Yes'
            return cleaned_data
            
        employee_type = cleaned_data.get('employee_type')
        reporting_manager = cleaned_data.get('reporting_manager')
        
        if 'employee_type' in self.data or 'reporting_manager' in self.data:
            if employee_type == 'EMPLOYEE':
                if not reporting_manager:
                    self.add_error('reporting_manager', "Reporting Manager is mandatory when Employee Type is Employee.")
            else:
                if reporting_manager:
                    cleaned_data['reporting_manager'] = None
                    
        # Check Need OT Check-In field validation
        try:
            enable_ot = admin_user.organization.enable_overtime
        except Exception:
            enable_ot = True
            
        if enable_ot and employee_type in ['HR_TEAM', 'MANAGER']:
            need_ot_check_in = cleaned_data.get('need_ot_check_in')
            if not need_ot_check_in:
                self.add_error('need_ot_check_in', "This field is mandatory for HR Team and Manager accounts.")
                
        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Check if need_ot_check_in changed
        old_status = profile.need_ot_check_in
        old_type = profile.employee_type
        
        profile.employee_type = self.cleaned_data['employee_type']
        profile.reporting_manager = self.cleaned_data.get('reporting_manager')
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.phone_number = self.cleaned_data.get('phone_number')
        user.gender = self.cleaned_data.get('gender')
        user.date_of_birth = self.cleaned_data.get('date_of_birth')
        user.current_address = self.cleaned_data.get('current_address')
        user.permanent_address = self.cleaned_data.get('permanent_address')
        user.city = self.cleaned_data.get('city')
        user.state = self.cleaned_data.get('state')
        user.country = self.cleaned_data.get('country')
        user.pincode = self.cleaned_data.get('pincode')
        user.nationality = self.cleaned_data.get('nationality')
        user.is_approved = (self.cleaned_data['status'] == 'ACTIVE')
        
        # Resolve need_ot_check_in
        admin_user = profile.created_by
        enable_ot = True
        enable_employee_types = True
        if admin_user:
            try:
                enable_ot = admin_user.organization.enable_overtime
                enable_employee_types = admin_user.organization.enable_employee_types
            except Exception:
                pass
                
        if not enable_ot:
            profile.need_ot_check_in = False
        elif not enable_employee_types:
            profile.need_ot_check_in = True
        else:
            emp_type = self.cleaned_data.get('employee_type', 'EMPLOYEE')
            if emp_type == 'EMPLOYEE':
                profile.need_ot_check_in = True
            else:
                profile.need_ot_check_in = (self.cleaned_data.get('need_ot_check_in', 'Yes') == 'Yes')
                
        # Set modified_by_username attribute so that the model's save() can log the modifier
        profile.modified_by_username = self.creator.username if self.creator else 'admin'
        
        if commit:
            user.save()
            profile.save()
        return profile
