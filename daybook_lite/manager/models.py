import logging
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

# Create your models here.
class Shop(models.Model):
    id = models.CharField(max_length=10, primary_key=True, default=_generate_shop_id, editable=False)
    short_name = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    d_no = models.CharField(max_length=10, null=True, blank=True, default='')
    addressline1 = models.CharField(max_length=255, null=True, blank=True, default='')
    addressline2 = models.CharField(max_length=255, null=True, blank=True, default='')
    place = models.CharField(max_length=50, null=True, blank=True)
    pincode = models.DecimalField(max_digits=6, decimal_places=0, null=True, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_local = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True) 
    port = models.PositiveIntegerField( null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(65535)])

    def __str__(self):
        return self.short_name


class Ledger(models.Model):
    id = models.CharField(max_length=10, primary_key=True, default=_generate_ledger_id, editable=False)
    name = models.CharField(max_length=50)
    license_number = models.CharField(max_length=50, blank=True, default='')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True, related_name='ledgers')

    def __str__(self):
        return self.name

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
        ACTIVITY_PURGE_DAYS = 'ACTIVITY_PURGE_DAYS', 'Activity Purge Days'

    # Default values for each key — blank unless specified
    DEFAULTS = {
        Key.D_REP_PAPER: 'A5',
        Key.D_REP_ORIENTATION: 'Portrait',
        Key.TRANS_PAPER: 'A5',
        Key.TRANS_ORIENTATION: 'Portrait',
        Key.LOAN_PAPER: 'A5',
        Key.LOAN_ORIENTATION: 'Portrait',
        Key.DEN_PURGE_DAYS: '7',
        Key.SESSION_TIMEOUT: '60',
        Key.ACTIVITY_PURGE_DAYS: '7'
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
        Key.ACTIVITY_PURGE_DAYS: Group.APP,
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
    action      = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name  = models.CharField(max_length=50, blank=True)  # e.g. 'Loan', 'Transaction'
    object_id   = models.CharField(max_length=50, blank=True)  # pk of affected record
    description = models.TextField(blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} | {self.action} | {self.model_name} | {self.created_at}"