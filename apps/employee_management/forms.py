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
        fields = ['employee_id', 'department', 'designation', 'date_of_joining', 'status', 'document', 'profile_image', 'shift', 'custom_check_in_time', 'custom_check_out_time']

    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator', None)
        super().__init__(*args, **kwargs)
        from apps.attendance.models import Shift
        if self.creator:
            self.fields['shift'].queryset = Shift.objects.filter(admin=self.creator, is_active=True)
        else:
            self.fields['shift'].queryset = Shift.objects.filter(is_active=True)

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

    def save(self, commit=True):
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
        fields = ['department', 'designation', 'date_of_joining', 'status', 'document', 'profile_image', 'shift', 'custom_check_in_time', 'custom_check_out_time']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.attendance.models import Shift
        if self.instance and self.instance.created_by:
            self.fields['shift'].queryset = Shift.objects.filter(admin=self.instance.created_by, is_active=True)
        else:
            self.fields['shift'].queryset = Shift.objects.filter(is_active=True)
            
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

    def save(self, commit=True):
        profile = super().save(commit=False)
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
        if commit:
            user.save()
            profile.save()
        return profile
