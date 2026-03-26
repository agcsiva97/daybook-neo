import datetime

from django import forms

from .models import Ledger, Shop

class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['short_name', 'is_local', 'name', 'd_no', 'addressline1', 'addressline2', 'place', 'pincode', 'balance', 'port','ip_address']
        labels = {
            'short_name': 'Short Name',
            'is_local': 'Is Local',
            'name': 'Shop Name',
            'd_no': 'D.No',
            'addressline1': 'Address Line 1',
            'addressline2': 'Address Line 2',
            'place': 'Place',
            'pincode': 'Pincode',
            'balance': 'Balance',
            'ip_address': 'IP Address',
            'port': 'Port',
        }
        widgets = {
            'short_name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            'is_local': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100'}),
            'd_no': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
            'addressline1': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '255'}),
            'addressline2': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '255'}),
            'place': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '50'}),
            'pincode': forms.NumberInput(attrs={'class': 'form-control', 'min': '100000', 'max': '999999'}),
            'balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '65535'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False
        self.fields['d_no'].required = False
        self.fields['addressline1'].required = False
        self.fields['addressline2'].required = False
        self.fields['place'].required = False
        self.fields['pincode'].required = False
        self.fields['balance'].required = False
        self.fields['ip_address'].required = False
        self.fields['port'].required = False


class ShopEditForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'is_local', 'd_no', 'addressline1', 'addressline2', 'place', 'pincode', 'balance']
        labels = {
            'name': 'Shop Name',
            'is_local': 'Is Local',
            'd_no': 'D.No',
            'addressline1': 'Address Line 1',
            'addressline2': 'Address Line 2',
            'place': 'Place',
            'pincode': 'Pincode',
            'balance': 'Balance',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100'}),
            'is_local': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'd_no': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
            'addressline1': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '255'}),
            'addressline2': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '255'}),
            'place': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '50'}),
            'pincode': forms.NumberInput(attrs={'class': 'form-control', 'min': '100000', 'max': '999999'}),
            'balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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