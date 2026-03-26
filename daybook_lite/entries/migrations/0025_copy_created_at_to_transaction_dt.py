from django.db import migrations

def copy_created_at(apps, schema_editor):
    # Migrate Loan model
    Loan = apps.get_model('entries', 'Loan')
    for loan in Loan.objects.all().iterator():  # .iterator() avoids loading all records into memory
        loan.transaction_dt = loan.created_at
        loan.save(update_fields=['transaction_dt'])

    # Migrate Transactions model
    Transactions = apps.get_model('entries', 'Transactions')
    for tr in Transactions.objects.all().iterator():
        tr.transaction_dt = tr.created_at
        tr.save(update_fields=['transaction_dt'])

def reverse_copy(apps, schema_editor):
    # Reverse migration — set transaction_dt back to null or skip
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0024_historicalloan_transaction_dt_and_more'),  # replace with actual last migration
    ]

    operations = [
        migrations.RunPython(copy_created_at, reverse_copy),
    ]