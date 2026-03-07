from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0009_historicalloan_historicaltransactions'),
    ]

    operations = [
        migrations.AddField(
            model_name='denomination',
            name='ledger',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='denominations',
                to='entries.ledger',
            ),
        ),
    ]
