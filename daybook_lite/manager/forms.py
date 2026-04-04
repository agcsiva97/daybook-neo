import datetime

from django import forms

from .models import Ledger, Shop, Accounts, Type

class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['short_name', 'name', 'proprietor', 'god', 'pan', 'd_no', 'addressline1', 'addressline2', 'place', 'pincode']
                #   'is_local', 'port','ip_address']
        labels = {
            'short_name': 'Short Name',
            # 'is_local': 'Is Local',
            'name': 'Shop Name',
            'proprietor': 'Proprietor Name',
            'god': 'God Name',
            'pan': 'PAN Number',
            'd_no': 'D.No',
            'addressline1': 'Address Line 1',
            'addressline2': 'Address Line 2',
            'place': 'Place',
            'pincode': 'Pincode',
            # 'balance': 'Balance',
            # 'ip_address': 'IP Address',
            # 'port': 'Port',
        }
        widgets = {
            'short_name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            # 'is_local': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100'}),
            'proprietor': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100'}),
            'god': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            'pan': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            'd_no': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
            'addressline1': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '255'}),
            'addressline2': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '255'}),
            'place': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '50'}),
            'pincode': forms.NumberInput(attrs={'class': 'form-control', 'min': '100000', 'max': '999999'}),
            # 'balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            # 'ip_address': forms.TextInput(attrs={'class': 'form-control'}),
            # 'port': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '65535'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False
        self.fields['proprietor'].required = False
        self.fields['god'].required = False
        self.fields['pan'].required = False
        self.fields['d_no'].required = False
        self.fields['addressline1'].required = False
        self.fields['addressline2'].required = False
        self.fields['place'].required = False
        self.fields['pincode'].required = False
        # self.fields['balance'].required = False
        # self.fields['ip_address'].required = False
        # self.fields['port'].required = False


class ShopEditForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'proprietor', 'god', 'pan', 'd_no', 'addressline1', 'addressline2', 'place', 'pincode']
        # , 'is_local'
        labels = {
            'name': 'Shop Name',
            'proprietor': 'Proprietor Name',
            'god': 'God Name',
            'pan': 'PAN Number',
            'is_local': 'Is Local',
            'd_no': 'D.No',
            'addressline1': 'Address Line 1',
            'addressline2': 'Address Line 2',
            'place': 'Place',
            'pincode': 'Pincode',
            # 'balance': 'Balance',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100'}),
            'proprietor': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100'}),
            'god': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            'pan': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            'is_local': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'd_no': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
            'addressline1': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '255'}),
            'addressline2': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '255'}),
            'place': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '50'}),
            'pincode': forms.NumberInput(attrs={'class': 'form-control', 'min': '100000', 'max': '999999'}),
            # 'balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proprietor'].required = False
        self.fields['god'].required = False
        self.fields['pan'].required = False
        self.fields['d_no'].required = False
        self.fields['addressline2'].required = False


class LedgerForm(forms.ModelForm):
    class Meta:
        model = Ledger
        fields = ['name', 'license_number']
        labels = {
            'name': 'Name',
            'license_number': 'License Number',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

class AccountsForm(forms.ModelForm):
    class Meta:
        model = Accounts
        fields = ['acc_type', 'e_name', 't_name', 'is_admin_only']
        widgets = {
            'e_name': forms.TextInput(attrs={'class': 'form-control'}),
            't_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Pop the shop from kwargs if you are passing it from the view
        shop = kwargs.pop('shop', None)
        super().__init__(*args, **kwargs)
        
        # Customize labels
        self.fields['acc_type'].label_from_instance = lambda obj: obj.t_name
        
        # 2. Update the queryset if a shop is provided
        if shop:
            self.fields['acc_type'].queryset = Type.objects.filter(shop=shop)
    
    # You don't necessarily need to redefine these if the Meta class handles them, 
    # but since you want specific widgets, keeping them is fine.
    acc_type = forms.ModelChoiceField(
        queryset=Type.objects.none(),
        required=True,
        empty_label='-- Select Type --',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_acc_type'}),
        label='Type',
    )

    date = forms.DateField(
        required=True,
        initial=datetime.date.today,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_date'}),
        label='Date',
    )

    time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(format='%H:%M:%S', attrs={'class': 'form-control', 'type': 'time', 'id': 'id_time','step': '1'}),
        label='Time',
    )
    
    # ✅ Extra field not in the model
    balance = forms.DecimalField(
        required=False,
        initial=0.00,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter balance'}),
        label='Balance',
    )

    is_admin_only = forms.BooleanField(
        required=False,
        label='Is Admin Only',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_admin_only'}),
    )

class AccountsEditForm(forms.ModelForm):
    class Meta:
        model = Accounts
        fields = ['acc_type', 'e_name', 't_name','is_admin_only']
        widgets = {
            'e_name': forms.TextInput(attrs={'class': 'form-control'}),
            't_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Pop the shop from kwargs if you are passing it from the view
        shop = kwargs.pop('shop', None)
        super().__init__(*args, **kwargs)
        
        # Customize labels
        self.fields['acc_type'].label_from_instance = lambda obj: obj.t_name
        
        # 2. Update the queryset if a shop is provided
        if shop:
            self.fields['acc_type'].queryset = Type.objects.filter(shop=shop)
    
    # You don't necessarily need to redefine these if the Meta class handles them, 
    # but since you want specific widgets, keeping them is fine.
    acc_type = forms.ModelChoiceField(
        queryset=Type.objects.none(),
        required=True,
        empty_label='-- Select Type --',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_acc_type'}),
        label='Type',
    )

    is_admin_only = forms.BooleanField(
        required=False,
        label='Is Admin Only',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_admin_only'}),
    )