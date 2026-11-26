from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import User, UserProfile

class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input-custom',
            'placeholder': 'Enter your username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input-custom',
            'placeholder': 'Enter your password'
        })
    )

class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}))
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

    class Meta:
        model = UserProfile
        fields = ['avatar', 'bio', 'address']
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'bio': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
            'address': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['phone_number'].initial = user.phone_number
            self.fields['gender'].initial = user.gender
            self.fields['date_of_birth'].initial = user.date_of_birth
            self.fields['current_address'].initial = user.current_address
            self.fields['permanent_address'].initial = user.permanent_address
            self.fields['city'].initial = user.city
            self.fields['state'].initial = user.state
            self.fields['country'].initial = user.country
            self.fields['pincode'].initial = user.pincode
            self.fields['nationality'].initial = user.nationality

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.phone_number = self.cleaned_data['phone_number']
        user.gender = self.cleaned_data['gender']
        user.date_of_birth = self.cleaned_data['date_of_birth']
        user.current_address = self.cleaned_data.get('current_address')
        user.permanent_address = self.cleaned_data.get('permanent_address')
        user.city = self.cleaned_data.get('city')
        user.state = self.cleaned_data.get('state')
        user.country = self.cleaned_data.get('country')
        user.pincode = self.cleaned_data.get('pincode')
        user.nationality = self.cleaned_data.get('nationality')
        if commit:
            user.save()
            profile.save()
            
            # Sync with EmployeeProfile if it exists
            try:
                if hasattr(user, 'employeeprofile'):
                    emp_profile = user.employeeprofile
                    if profile.avatar:
                        emp_profile.profile_image = profile.avatar
                    emp_profile.save()
            except Exception:
                pass
        return profile
