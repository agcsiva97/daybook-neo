import datetime

from django import forms

from .models import Ledger, Shop, Transactions, Denomination, Loan


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['short_name', 'name', 'd_no', 'addressline1', 'addressline2', 'place', 'pincode', 'balance']
        labels = {
            'short_name': 'Short Name',
            'name': 'Shop Name',
            'd_no': 'D.No',
            'addressline1': 'Address Line 1',
            'addressline2': 'Address Line 2',
            'place': 'Place',
            'pincode': 'Pincode',
            'balance': 'Balance',
        }
        widgets = {
            'short_name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '20'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100'}),
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


class ShopEditForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'd_no', 'addressline1', 'addressline2', 'place', 'pincode', 'balance']
        labels = {
            'name': 'Shop Name',
            'd_no': 'D.No',
            'addressline1': 'Address Line 1',
            'addressline2': 'Address Line 2',
            'place': 'Place',
            'pincode': 'Pincode',
            'balance': 'Balance',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '100'}),
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


class TransactionForm(forms.ModelForm):
    TR_TYPE_CHOICES = [
        ('DEBIT', 'DEBIT'),
        ('CREDIT', 'CREDIT'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize shop dropdown to display short_name
        self.fields['shop'].label_from_instance = lambda obj: obj.short_name

    shop = forms.ModelChoiceField(
        queryset=Shop.objects.all().order_by('short_name'),
        required=True,
        empty_label='-- Select Shop --',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_shop'}),
        label='Shop',
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
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time', 'id': 'id_time'}),
        label='Time',
    )

    class Meta:
        model = Transactions
        fields = ['amount', 'name', 'shop', 'tr_type', 'remarks']
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
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time', 'id': 'loan_time'}),
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
        # If instance exists, filter ledgers by its shop
        if self.instance and self.instance.pk and self.instance.ledger:
            shop = self.instance.ledger.shop
            if shop:
                self.fields['ledger'].queryset = Ledger.objects.filter(shop=shop).order_by('name')
                self.fields['shop'].initial = shop
        # Remove empty_label from ledger
        self.fields['ledger'].empty_label = None

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
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
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
