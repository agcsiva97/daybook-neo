import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0010_denomination_ledger'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transactions',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='historicaltransactions',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
