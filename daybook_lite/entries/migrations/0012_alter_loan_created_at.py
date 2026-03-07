import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0011_alter_transactions_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='loan',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='historicalloan',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
