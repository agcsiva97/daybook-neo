from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm as DjangoUserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


class UserCreationForm(DjangoUserCreationForm):
    first_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}), label='First Name *')
    last_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}), label='Last Name *')
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}), label='Email *')
    mobile_number = forms.CharField(max_length=10, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter 10 digit mobile number'}), label='Mobile Number')
    alternate_number = forms.CharField(max_length=10, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter 10 digit alternate number'}), label='Alternate Number')
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=True, widget=forms.Select(attrs={'class': 'form-select'}), label='Group *')
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'mobile_number', 'alternate_number', 'password1', 'password2', 'group']
        labels = {
            'username': 'Username *',
            'password1': 'Password *',
            'password2': 'Confirm Password *',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm password'})
        self.fields['password1'].label = 'Password *'
        self.fields['password2'].label = 'Confirm Password *'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.mobile_number = self.cleaned_data.get('mobile_number', '')
        user.alternate_number = self.cleaned_data.get('alternate_number', '')
        if commit:
            user.save()
            group = self.cleaned_data['group']
            user.groups.add(group)
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'mobile_number', 'alternate_number']
        labels = {
            'first_name': 'First Name *',
            'last_name': 'Last Name *',
            'email': 'Email *',
            'mobile_number': 'Mobile Number',
            'alternate_number': 'Alternate Number',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter 10 digit mobile number'}),
            'alternate_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter 10 digit alternate number'}),
        }


class UserEditForm(forms.ModelForm):
    """Form for admin users to edit other users' information"""
    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Group *'
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'mobile_number', 'alternate_number', 'group']
        labels = {
            'first_name': 'First Name *',
            'last_name': 'Last Name *',
            'email': 'Email *',
            'mobile_number': 'Mobile Number',
            'alternate_number': 'Alternate Number',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter 10 digit mobile number'}),
            'alternate_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter 10 digit alternate number'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Set initial group value if user already has groups
            user_groups = self.instance.groups.all()
            if user_groups.exists():
                self.fields['group'].initial = user_groups.first()
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Update group membership
            user.groups.clear()
            group = self.cleaned_data['group']
            user.groups.add(group)
        return user


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})
        self.fields['old_password'].label = 'Old Password *'
        self.fields['new_password1'].label = 'New Password *'
        self.fields['new_password2'].label = 'Confirm New Password *'
