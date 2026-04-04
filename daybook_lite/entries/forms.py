import datetime

from django import forms

from .models import Ledger, Shop, Transactions, Denomination, Loan
from manager.models import Accounts

class TransactionForm(forms.ModelForm):
    TR_TYPE_CHOICES = [
        ('DEBIT', 'DEBIT'),
        ('CREDIT', 'CREDIT'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize shop dropdown to display short_name
        self.fields['shop'].label_from_instance = lambda obj: obj.short_name
        # Customize account dropdown to display t_name
        self.fields['acc'].label_from_instance = lambda obj: obj.t_name if obj.t_name else obj.e_name

    shop = forms.ModelChoiceField(
        queryset=Shop.objects.all().order_by('short_name'),
        required=True,
        empty_label='-- Select Shop --',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_shop'}),
        label='Shop',
    )

    acc = forms.ModelChoiceField(
        queryset=Accounts.objects.all(),
        required=True,
        empty_label='-- Select Account --',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_account'}),
        label='Account',
    )


    tr_type = forms.ChoiceField(
        choices=TR_TYPE_CHOICES,
        widget=forms.RadioSelect,
        label='Transaction Type',
    )

    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter name'}),
        label='Name',
    )

    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter remarks'}),
        label='Remarks',
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

    class Meta:
        model = Transactions
        fields = ['amount', 'name', 'shop', 'acc', 'tr_type', 'remarks']
        labels = {
            'amount': 'Amount',
        }
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Enter amount'}),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        # Make name required for new transactions
        if not self.instance.pk and not name:
            raise forms.ValidationError('This field is required.')
        return name
    
    def clean_remarks(self):
        remarks = self.cleaned_data.get('remarks')
        # Make remarks required for new transactions
        if not self.instance.pk and not remarks:
            raise forms.ValidationError('This field is required.')
        return remarks


class TransactionEditForm(forms.ModelForm):
    """Edit form for transactions with user-aware account filtering"""
    TR_TYPE_CHOICES = [
        ('DEBIT', 'DEBIT'),
        ('CREDIT', 'CREDIT'),
    ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize shop dropdown to display short_name
        self.fields['shop'].label_from_instance = lambda obj: obj.short_name
        
        # Determine if user is admin or superuser
        is_admin_or_superuser = user and (user.is_superuser or user.groups.filter(name='Admin').exists())
        
        # Determine the shop to filter accounts by
        shop_for_filter = None
        if self.data and 'shop' in self.data:
            # POST data has shop - use it
            try:
                shop_for_filter = Shop.objects.get(pk=self.data['shop'])
            except (ValueError, Shop.DoesNotExist):
                pass
        elif self.instance and self.instance.pk and self.instance.shop:
            # GET or initial - use instance's shop
            shop_for_filter = self.instance.shop
        
        if shop_for_filter:
            # Filter accounts for the selected shop
            accounts_qs = Accounts.objects.filter(shop=shop_for_filter).order_by('-priority')
            # If not admin/superuser, exclude admin-only accounts
            if not is_admin_or_superuser:
                accounts_qs = accounts_qs.filter(is_admin_only=False)
            self.fields['acc'].queryset = accounts_qs
            if not self.data:  # Only set initial for GET
                self.fields['shop'].initial = shop_for_filter
        else:
            # Fallback - all accounts (filtered by admin status)
            accounts_qs = Accounts.objects.all().order_by('-priority')
            if not is_admin_or_superuser:
                accounts_qs = accounts_qs.filter(is_admin_only=False)
            self.fields['acc'].queryset = accounts_qs
        
        # Customize account dropdown to display t_name
        self.fields['acc'].label_from_instance = lambda obj: obj.t_name if obj.t_name else obj.e_name

    shop = forms.ModelChoiceField(
        queryset=Shop.objects.all().order_by('short_name'),
        required=True,
        empty_label='-- Select Shop --',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_shop'}),
        label='Shop',
    )

    acc = forms.ModelChoiceField(
        queryset=Accounts.objects.all(),
        required=True,
        empty_label='-- Select Account --',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_account'}),
        label='Account',
    )

    tr_type = forms.ChoiceField(
        choices=TR_TYPE_CHOICES,
        widget=forms.RadioSelect,
        label='Transaction Type',
    )

    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter name'}),
        label='Name',
    )

    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter remarks'}),
        label='Remarks',
    )

    date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_date'}),
        label='Date',
    )

    time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(format='%H:%M:%S', attrs={'class': 'form-control', 'type': 'time', 'id': 'id_time','step': '1'}),
        label='Time',
    )

    class Meta:
        model = Transactions
        fields = ['amount', 'name', 'shop', 'acc', 'tr_type', 'remarks']
        labels = {
            'amount': 'Amount',
        }
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Enter amount'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        shop = cleaned_data.get('shop')
        acc = cleaned_data.get('acc')
        
        if shop and acc:
            if acc.shop != shop:
                raise forms.ValidationError("The selected account does not belong to the selected shop.")
        
        return cleaned_data


class TransferForm(forms.Form):
    from_ledger = forms.ModelChoiceField(
        queryset=Ledger.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_from_ledger'}),
        label='From Ledger',
    )
    to_ledger = forms.ModelChoiceField(
        queryset=Ledger.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_to_ledger'}),
        label='To Ledger',
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Enter amount'}),
        label='Amount',
    )
    # name = forms.CharField(
    #     required=True,
    #     widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter name'}),
    #     label='Name',
    # )
    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter remarks (optional)'}),
        label='Remarks',
    )

    def clean(self):
        cleaned_data = super().clean()
        from_ledger = cleaned_data.get('from_ledger')
        to_ledger = cleaned_data.get('to_ledger')

        if from_ledger and to_ledger and from_ledger == to_ledger:
            raise forms.ValidationError("From Ledger and To Ledger cannot be the same.")

        return cleaned_data

class DenominationForm(forms.Form):
    shop = forms.ModelChoiceField(
        queryset=Shop.objects.all().order_by('name'),
        required=True,
        empty_label='-- Select Shop --',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Shop',
    )
    time_period = forms.ChoiceField(
        choices=Denomination.TIME_PERIOD_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Time Period',
    )
    
    note_2000 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='2000 x',
    )
    note_500 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='500 x',
    )
    note_200 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='200 x',
    )
    note_100 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='100 x',
    )
    note_50 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='50 x',
    )
    note_20 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='20 x',
    )
    note_10 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='10 x',
    )
    coins = forms.DecimalField(
        required=False,
        min_value=0,
        initial=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
        label='Coins',
    )
    damage = forms.DecimalField(
        required=False,
        min_value=0,
        initial=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
        label='Damage',
    )
    inside = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='Inside',
    )
    bundle_500 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='500 Bundle x',
    )
    bundle_200 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='200 Bundle x',
    )
    bundle_100 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='100 Bundle x',
    )
    bundle_50 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='50 Bundle x',
    )
    bundle_20 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='20 Bundle x',
    )
    bundle_10 = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        label='10 Bundle x',
    )


class LoanForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize shop dropdown to display short_name
        self.fields['shop'].label_from_instance = lambda obj: obj.short_name

    date = forms.DateField(
        required=True,
        initial=datetime.date.today,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'loan_date'}),
        label='Date',
    )

    time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(format='%H:%M:%S.%f', attrs={'class': 'form-control', 'type': 'time', 'id': 'loan_time','step': '0.001'}),
        label='Time',
    )

    shop = forms.ModelChoiceField(
        queryset=Shop.objects.all().order_by('short_name'),
        required=True,
        empty_label='-- Select Shop --',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'loan_shop'}),
        label='Shop',
    )

    pawn_no = forms.CharField(
        required=True,
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Pawn No', 'id': 'loan_pawn_no'}),
        label='Pawn No',
    )
    principal = forms.DecimalField(
        required=True,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00', 'id': 'loan_principal'}),
        label='Principal',
    )
    interest = forms.DecimalField(
        required=True,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00', 'id': 'loan_interest'}),
        label='Interest',
    )
    ledger = forms.ModelChoiceField(
        queryset=Ledger.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'loan_ledger'}),
        label='Ledger',
    )


class LoanEditForm(forms.ModelForm):
    TYPE_CHOICES = [
        ('LOAN', 'Loan'),
        ('RELEASE', 'Release'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize shop dropdown to display short_name
        self.fields['shop'].label_from_instance = lambda obj: obj.short_name
        
        # Determine the shop to filter ledgers by
        shop_for_filter = None
        if self.data and 'shop' in self.data:
            # POST data has shop - use it
            try:
                shop_for_filter = Shop.objects.get(pk=self.data['shop'])
            except (ValueError, Shop.DoesNotExist):
                pass
        elif self.instance and self.instance.pk and self.instance.ledger:
            # GET or initial - use instance's shop
            shop_for_filter = self.instance.ledger.shop
        
        if shop_for_filter:
            self.fields['ledger'].queryset = Ledger.objects.filter(shop=shop_for_filter).order_by('name')
            if not self.data:  # Only set initial for GET
                self.fields['shop'].initial = shop_for_filter
        else:
            # Fallback - all ledgers
            self.fields['ledger'].queryset = Ledger.objects.all().order_by('name')
        
        # Remove empty_label from ledger
        self.fields['ledger'].empty_label = None

    def clean(self):
        cleaned_data = super().clean()
        shop = cleaned_data.get('shop')
        ledger = cleaned_data.get('ledger')
        
        if shop and ledger:
            if ledger.shop != shop:
                raise forms.ValidationError("The selected ledger does not belong to the selected shop.")
        
        return cleaned_data

    shop = forms.ModelChoiceField(
        queryset=Shop.objects.all().order_by('short_name'),
        required=True,
        empty_label='-- Select Shop --',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'edit_loan_shop'}),
        label='Shop',
    )

    type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        widget=forms.RadioSelect,
        label='Transaction Type',
    )

    date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Date',
    )

    time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(format='%H:%M:%S', attrs={'class': 'form-control', 'type': 'time','step': '1'}),
        label='Time',
    )

    class Meta:
        model = Loan
        fields = ['pawn_no', 'ledger', 'type', 'principal', 'interest']
        labels = {
            'pawn_no': 'Pawn No',
            'ledger': 'Ledger',
            'principal': 'Principal',
            'interest': 'Interest',
        }
        widgets = {
            'pawn_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Pawn No'}),
            'ledger': forms.Select(attrs={'class': 'form-control', 'id': 'edit_loan_ledger'}),
            'principal': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'interest': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
        }
