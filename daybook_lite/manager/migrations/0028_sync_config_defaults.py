from django.db import migrations
import logging

logger = logging.getLogger(__name__)

KEYS_TO_ADD = {
    'DEFAULT_SHOP': {'group': 'APP', 'value': ''},
}

KEYS_TO_REMOVE = [
    'ACTIVITY_PURGE_DAYS',  # renamed/removed keys go here
]

def sync_config_keys(apps, schema_editor):
    Configuration = apps.get_model('manager', 'Configuration')

    # Add new keys if not present
    for key, meta in KEYS_TO_ADD.items():
        obj, created = Configuration.objects.get_or_create(
            key=key,
            defaults={'group': meta['group'], 'value': meta['value']}
        )
        if created:
            print(f"[Config Migration] Created key=[{key}]")
        else:
            print(f"[Config Migration] Already exists key=[{key}] — skipped")

    # Remove old/renamed keys
    for key in KEYS_TO_REMOVE:
        deleted, _ = Configuration.objects.filter(key=key).delete()
        if deleted:
            print(f"[Config Migration] Removed key=[{key}]")
        else:
            print(f"[Config Migration] Key not found key=[{key}] — skipped")

def reverse_sync_config_keys(apps, schema_editor):
    """Reverse: remove added keys, restore removed keys."""
    Configuration = apps.get_model('manager', 'Configuration')
    for key in KEYS_TO_ADD:
        Configuration.objects.filter(key=key).delete()
    for key, meta in {  # restore old keys if needed
        'ACTIVITY_PURGE_DAYS': {'group': 'DBK', 'value': '7'},
    }.items():
        Configuration.objects.get_or_create(
            key=key,
            defaults={'group': meta['group'], 'value': meta['value']}
        )

class Migration(migrations.Migration):

    dependencies = [
        ('manager', '0027_alter_configuration_key'),
    ]

    operations = [
        migrations.RunPython(sync_config_keys, reverse_sync_config_keys),
    ]
