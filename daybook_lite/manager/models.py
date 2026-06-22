import logging
import re
import uuid

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

logger = logging.getLogger(__name__)
    

# Create your models here.
def _generate_shop_id():
    """Generate a unique 8-char shop ID: SHP + 5 random alphanumeric chars."""
    return 'SHP' + uuid.uuid4().hex[:5].upper()

def _generate_ledger_id():
    """Generate a unique 8-char ledger ID: LED + 5 random alphanumeric chars."""
    return 'LED' + uuid.uuid4().hex[:5].upper()

def _generate_type_id():
    """Generate a unique 8-char type ID: TYP + 5 random alphanumeric chars."""
    return 'TYP' + uuid.uuid4().hex[:5].upper()

def _generate_accounts_id():
    """Generate a unique 8-char accounts ID: ACC + 5 random alphanumeric chars."""
    return 'ACC' + uuid.uuid4().hex[:5].upper()

def _generate_bt_id():
    """Generate a unique 8-char BT ID: BT + 5 random alphanumeric chars."""
    return 'BT' + uuid.uuid4().hex[:5].upper()

# Create your models here.
class Shop(models.Model):
    id = models.CharField(max_length=10, primary_key=True, default=_generate_shop_id, editable=False)
    short_name = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    proprietor = models.CharField(max_length=100, null=True, blank=True, default='')
    god = models.CharField(max_length=100, null=True, blank=True, default='')  # GST / GOD number
    pan = models.CharField(max_length=20, null=True, blank=True, default='')  # PAN number
    d_no = models.CharField(max_length=10, null=True, blank=True, default='')
    addressline1 = models.CharField(max_length=255, null=True, blank=True, default='')
    addressline2 = models.CharField(max_length=255, null=True, blank=True, default='')
    place = models.CharField(max_length=50, null=True, blank=True)
    pincode = models.DecimalField(max_digits=6, decimal_places=0, null=True, blank=True)
    last_transaction_exported_at = models.DateTimeField(null=True, blank=True)
    last_transaction_imported_at = models.DateTimeField(null=True, blank=True)
    last_loans_exported_at = models.DateTimeField(null=True, blank=True)
    last_loans_imported_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.short_name


class Ledger(models.Model):
    id = models.CharField(max_length=10, primary_key=True, default=_generate_ledger_id, editable=False)
    name = models.CharField(max_length=50)
    license_number = models.CharField(max_length=50, blank=True, default='')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True, related_name='ledgers')

    def __str__(self):
        return self.name


class Type(models.Model):
    id = models.CharField(max_length=10, primary_key=True, default=_generate_type_id, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True, related_name='types')
    e_name = models.CharField(max_length=50, blank=True, default='')
    t_name = models.CharField(max_length=50, blank=True, default='')
    group_order = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(6)])

    def __str__(self):
        return self.e_name

class Accounts(models.Model):
    id = models.CharField(max_length=10, primary_key=True, default=_generate_accounts_id, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True, related_name='shop_accounts')
    e_name = models.CharField(max_length=50, blank=True, default='')
    t_name = models.CharField(max_length=50, blank=True, default='')
    acc_type = models.ForeignKey(Type, on_delete=models.CASCADE, null=True, blank=True, related_name='accounts')
    priority = models.PositiveIntegerField(default=0)
    is_admin_only = models.BooleanField(default=False)

    def __str__(self):
        return self.e_name

class Configuration(models.Model):
    class Group(models.TextChoices):
        DBK = 'DBK', 'Daybook'
        APP = 'APP', 'Application'

    class Key(models.TextChoices):
        # Daybook configuration keys
        D_REP_PAPER         = 'D_REP_PAPER',         'Daily Report Paper Size'
        D_REP_ORIENTATION = 'D_REP_ORIENTATION',   'Daily Report Orientation'
        TRANS_PAPER         = 'TRANS_PAPER',         'Transaction Paper Size'
        TRANS_ORIENTATION = 'TRANS_ORIENTATION',   'Transaction Orientation'
        LOAN_PAPER         = 'LOAN_PAPER',         'Loan Paper Size'
        LOAN_ORIENTATION = 'LOAN_ORIENTATION',   'Loan Orientation'
        DEN_PURGE_DAYS = 'DEN_PURGE_DAYS', 'Denomination Purge Days'
        SESSION_TIMEOUT = 'SESSION_TIMEOUT', 'Session Timeout in Seconds'
        DEFAULT_SHOP = 'DEFAULT_SHOP', 'Default Shop short name'

    # Default values for each key — blank unless specified
    DEFAULTS = {
        Key.D_REP_PAPER: 'A5',
        Key.D_REP_ORIENTATION: 'Portrait',
        Key.TRANS_PAPER: 'A5',
        Key.TRANS_ORIENTATION: 'Portrait',
        Key.LOAN_PAPER: 'A5',
        Key.LOAN_ORIENTATION: 'Portrait',
        Key.DEN_PURGE_DAYS: '7',
        Key.SESSION_TIMEOUT: '1800',
        Key.DEFAULT_SHOP: ''
    }

    # Maps each key to its group
    KEY_GROUP_MAP = {
        Key.D_REP_PAPER: Group.DBK,
        Key.D_REP_ORIENTATION: Group.DBK,
        Key.TRANS_PAPER: Group.DBK,
        Key.TRANS_ORIENTATION: Group.DBK,
        Key.LOAN_PAPER: Group.DBK,
        Key.LOAN_ORIENTATION: Group.DBK,
        Key.DEN_PURGE_DAYS: Group.DBK,
        Key.SESSION_TIMEOUT: Group.APP,
        Key.DEFAULT_SHOP: Group.APP,
    }

    group = models.CharField(max_length=50, choices=Group.choices)
    key   = models.CharField(max_length=50, choices=Key.choices, unique=True)
    value = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['group', 'key']

    def __str__(self):
        return f"{self.group} -> {self.key}: {self.value}"

    @classmethod
    def initialize_defaults(cls):
        """
        Create default config rows for all keys that don't exist yet.
        Safe to run multiple times — skips existing keys.
        Use this for first-time setup AND when adding new keys.
        """
        created_count = 0
        skipped_count = 0

        for key, group in cls.KEY_GROUP_MAP.items():
            default_value = cls.DEFAULTS.get(key, '')
            obj, created = cls.objects.get_or_create(
                key=key,
                defaults={
                    'group': group,
                    'value': default_value,
                }
            )
            if created:
                logger.info(f"[Config] Created -> group=[{group}] | key=[{key}] | value=[{default_value}]")
                created_count += 1
            else:
                logger.info(f"[Config] Skipped (exists) -> key=[{key}]")
                skipped_count += 1

        logger.info(f"[Config] Initialization complete -> created=[{created_count}] | skipped=[{skipped_count}]")

    @classmethod
    def get_value(cls, key, default=None):
        """Fetch a single config value by key."""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            logger.warning(f"[Config] Key not found -> key=[{key}] | using default=[{default}]")
            return default


# manager/models.py
class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN',  'Login'),
        ('LOGOUT', 'Logout'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW',   'View'),
    ]
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    shop        = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True)
    action      = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name  = models.CharField(max_length=50, blank=True)  # e.g. 'Loan', 'Transaction'
    object_id   = models.CharField(max_length=50, blank=True)  # pk of affected record
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} | {self.action} | {self.model_name} | {self.created_at}"

class ExportHistory(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='export_histories')
    export_type = models.CharField(max_length=20)  # e.g. 'transactions', 'loans'
    exported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-exported_at']

    def __str__(self):
        return f"{self.shop.short_name} | {self.export_type} | {self.exported_at}"
    
class ExportDetails(models.Model):
    export_history = models.ForeignKey(ExportHistory, on_delete=models.CASCADE, related_name='details')
    record_id = models.CharField(max_length=50)  # ID of the exported record
    record_type = models.CharField(max_length=20)  # e.g. 'transaction', 'loan'
    status = models.CharField(max_length=20)  # e.g. 'success', 'failed'
    message = models.TextField(blank=True)  # Optional message for failures or additional info

    def __str__(self):
        return f"{self.export_history.shop.short_name} | {self.record_type} | {self.record_id} | {self.status}"
    
class ImportHistory(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='import_histories')
    import_type = models.CharField(max_length=20)  # e.g. 'transactions', 'loans'
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-imported_at']

    def __str__(self):
        return f"{self.shop.short_name} | {self.import_type} | {self.imported_at}"
    
class ImportDetails(models.Model):
    import_history = models.ForeignKey(ImportHistory, on_delete=models.CASCADE, related_name='details')
    record_id = models.CharField(max_length=50)  # ID of the imported record
    record_type = models.CharField(max_length=20)  # e.g. 'transaction', 'loan'
    status = models.CharField(max_length=20)  # e.g. 'success', 'failed'
    message = models.TextField(blank=True)  # Optional message for failures or additional info

    def __str__(self):
        return f"{self.import_history.shop.short_name} | {self.record_type} | {self.record_id} | {self.status}"
    
class BT_Ledger_Accounts(models.Model):
    id = models.CharField(max_length=30, primary_key=True, editable=False, default=_generate_bt_id)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True, related_name='bt_ledger_accounts')
    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE)
    rel_type = models.CharField(max_length=25, blank=False)  # e.g. 'PRIMARY', 'SECONDARY', etc.
    account = models.ForeignKey(Accounts, on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_bt_ledger_accounts',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_bt_ledger_accounts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.shop.short_name} - {self.ledger.name} - {self.account.e_name}"

    def save(self, *args, **kwargs):
        if not self.id:
            shop_name = self.shop.short_name if self.shop_id and self.shop else 'BTL'
            self.id = _generate_bt_id(shop_name)
        super().save(*args, **kwargs)    
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['ledger', 'rel_type'], name='unique_ledger_rel_type')
        ]