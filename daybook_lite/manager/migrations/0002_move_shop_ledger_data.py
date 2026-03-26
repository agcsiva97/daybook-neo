from django.db import migrations

def move_data_forward(apps, schema_editor):
    # Data already exists in manager models, skip copying
    pass

def move_data_backward(apps, schema_editor):
    # Data migration is not reversible since data already exists
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('manager', '0001_initial'),
        # Data already copied, no dependency needed
    ]

    operations = [
        migrations.RunPython(move_data_forward, move_data_backward),
    ]