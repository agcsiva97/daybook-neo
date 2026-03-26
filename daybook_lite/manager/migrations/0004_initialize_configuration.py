# manager/migrations/xxxx_initialize_configuration.py
from django.db import migrations

def initialize_config(apps, schema_editor):
    # Use the actual model to call the method
    from manager.models import Configuration
    Configuration.initialize_defaults()

def reverse_config(apps, schema_editor):
    Configuration = apps.get_model('manager', 'Configuration')
    Configuration.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('manager', '0003_configuration_model'),
    ]

    operations = [
        migrations.RunPython(initialize_config, reverse_config),
    ]
