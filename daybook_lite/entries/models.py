import random
import re
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


def generate_custom_id(ledger_name):
    """Generate a custom ID: <LEDGER_PREFIX><DDMMYY><HHMMSSMMM>-<6-digit-random>
    e.g. TLB0202260555321100-359612
    """
    now = timezone.localtime(timezone.now())
    prefix = re.sub(r'[^A-Z0-9]', '', ledger_name.upper())[:3].ljust(3, 'X')
    date_part = now.strftime('%d%m%y')                             # DDMMYY
    time_part = now.strftime('%H%M%S') + f'{now.microsecond // 1000:03d}'  # HHMMSSMMM
    rand_part = f'{random.randint(0, 999999):06d}'
    return f'{prefix}{date_part}{time_part}-{rand_part}'


# Create your models here.
def _generate_shop_id():
    """Generate a unique 8-char shop ID: SHP + 5 random alphanumeric chars."""
    return 'SHP' + uuid.uuid4().hex[:5].upper()


class Shop(models.Model):
    id = models.CharField(max_length=10, primary_key=True, default=_generate_shop_id, editable=False)
    short_name = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    d_no = models.CharField(max_length=10, blank=True, default='')
    addressline1 = models.CharField(max_length=255)
    addressline2 = models.CharField(max_length=255, blank=True, default='')
    place = models.CharField(max_length=50)
    pincode = models.DecimalField(max_digits=6, decimal_places=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.short_name


class Ledger(models.Model):
    name = models.CharField(max_length=50)
    license_number = models.CharField(max_length=50, blank=True, default='')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True, related_name='ledgers')

    def __str__(self):
        return self.name
    
class Transactions(models.Model):
    id = models.CharField(max_length=30, primary_key=True, editable=False)
    amount = models.DecimalField(decimal_places=2, max_digits=12)
    name = models.TextField(blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True, related_name='transactions')
    tr_type = models.CharField(max_length=10)
    remarks = models.TextField(blank=True)
    old_balance = models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)
    new_balance = models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_transactions',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_transactions',
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)
    history = HistoricalRecords()
    
    def __str__(self):
        return str(self.amount)

    def save(self, *args, **kwargs):
        if not self.id:
            shop_name = self.shop.name if self.shop_id and self.shop else 'TRN'
            self.id = generate_custom_id(shop_name)
        super().save(*args, **kwargs)

class Denomination(models.Model):
    id = models.CharField(max_length=30, primary_key=True, editable=False)
    TIME_PERIOD_CHOICES = [
        ('MORNING', 'Morning'),
        ('AFTERNOON', 'Afternoon'),
        ('EVENING', 'Evening'),
        ('NIGHT', 'Night'),
    ]
    
    denomination = models.CharField(max_length=50)
    count = models.IntegerField()
    amount = models.DecimalField(decimal_places=2, max_digits=12)
    time_period = models.CharField(max_length=20, choices=TIME_PERIOD_CHOICES, default='Night')
    key = models.CharField(max_length=100, default='MMDDYYYY-XX-username')
    shop = models.ForeignKey(
        'Shop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='denominations',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_denominations',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_denominations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.denomination} x {self.count}"

    def save(self, *args, **kwargs):
        if not self.id:
            shop_name = self.shop.name if self.shop_id and self.shop else 'DEN'
            self.id = generate_custom_id(shop_name)
        super().save(*args, **kwargs)


class Loan(models.Model):
    id = models.CharField(max_length=30, primary_key=True, editable=False)
    TYPE_CHOICES = [
        ('LOAN', 'Loan'),
        ('RELEASE', 'Release'),
    ]
    
    pawn_no = models.CharField(max_length=10)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True, related_name='loans')
    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    principal = models.DecimalField(decimal_places=2, max_digits=12)
    interest = models.DecimalField(decimal_places=2, max_digits=12)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_loans',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_loans',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.pawn_no} - {self.ledger.name}"

    def save(self, *args, **kwargs):
        if not self.id:
            ledger_name = self.ledger.name if self.ledger_id and self.ledger else 'LON'
            self.id = generate_custom_id(ledger_name)
        super().save(*args, **kwargs)
