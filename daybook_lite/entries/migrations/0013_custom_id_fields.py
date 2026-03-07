import random
import re

from django.db import migrations, models


def _make_id(ledger_name, created_at):
    prefix = re.sub(r'[^A-Z0-9]', '', ledger_name.upper())[:3].ljust(3, 'X')
    date_part = created_at.strftime('%d%m%y')
    time_part = created_at.strftime('%H%M%S') + f'{created_at.microsecond // 1000:03d}'
    rand_part = f'{random.randint(0, 999999):06d}'
    return f'{prefix}{date_part}{time_part}-{rand_part}'


def reassign_existing_ids(apps, schema_editor):
    """Update existing integer-string PKs to the proper custom ID format."""
    from django.db import connection
    from django.utils import timezone

    with connection.cursor() as c:
        # --- Transactions ---
        c.execute(
            "SELECT t.id, l.name, t.created_at "
            "FROM entries_transactions t "
            "LEFT JOIN entries_ledger l ON l.id = t.ledger_id"
        )
        for row in c.fetchall():
            old_id, ledger_name, created_at_raw = row
            # Only update records still carrying the old integer-style ID
            try:
                int(old_id)
            except (ValueError, TypeError):
                continue
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(str(created_at_raw)) if created_at_raw else timezone.now()
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            dt = dt or timezone.now()
            new_id = _make_id(ledger_name or 'TRN', timezone.localtime(dt))
            c.execute(
                "UPDATE entries_transactions SET id = %s WHERE id = %s",
                [new_id, old_id],
            )
            c.execute(
                "UPDATE entries_historicaltransactions SET id = %s WHERE id = %s",
                [new_id, old_id],
            )

        # --- Denomination ---
        c.execute(
            "SELECT d.id, l.name, d.created_at "
            "FROM entries_denomination d "
            "LEFT JOIN entries_ledger l ON l.id = d.ledger_id"
        )
        for row in c.fetchall():
            old_id, ledger_name, created_at_raw = row
            try:
                int(old_id)
            except (ValueError, TypeError):
                continue
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(str(created_at_raw)) if created_at_raw else timezone.now()
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            dt = dt or timezone.now()
            new_id = _make_id(ledger_name or 'DEN', timezone.localtime(dt))
            c.execute(
                "UPDATE entries_denomination SET id = %s WHERE id = %s",
                [new_id, old_id],
            )

        # --- Loan ---
        c.execute(
            "SELECT lo.id, l.name, lo.created_at "
            "FROM entries_loan lo "
            "LEFT JOIN entries_ledger l ON l.id = lo.ledger_id"
        )
        for row in c.fetchall():
            old_id, ledger_name, created_at_raw = row
            try:
                int(old_id)
            except (ValueError, TypeError):
                continue
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(str(created_at_raw)) if created_at_raw else timezone.now()
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            dt = dt or timezone.now()
            new_id = _make_id(ledger_name or 'LON', timezone.localtime(dt))
            c.execute(
                "UPDATE entries_loan SET id = %s WHERE id = %s",
                [new_id, old_id],
            )
            c.execute(
                "UPDATE entries_historicalloan SET id = %s WHERE id = %s",
                [new_id, old_id],
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0012_alter_loan_created_at'),
    ]

    operations = [
        # --- Transactions ---
        migrations.AlterField(
            model_name='transactions',
            name='id',
            field=models.CharField(editable=False, max_length=30, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='historicaltransactions',
            name='id',
            field=models.CharField(db_index=True, editable=False, max_length=30),
        ),
        # --- Denomination ---
        migrations.AlterField(
            model_name='denomination',
            name='id',
            field=models.CharField(editable=False, max_length=30, primary_key=True, serialize=False),
        ),
        # --- Loan ---
        migrations.AlterField(
            model_name='loan',
            name='id',
            field=models.CharField(editable=False, max_length=30, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='historicalloan',
            name='id',
            field=models.CharField(db_index=True, editable=False, max_length=30),
        ),
        # Backfill existing records
        migrations.RunPython(reassign_existing_ids, reverse_code=noop),
    ]
