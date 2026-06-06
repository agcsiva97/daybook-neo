from django.db import migrations


def create_system_user(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.get_or_create(
        username='system',
        defaults={
            'first_name': 'System',
            'last_name':  'Automated',
            'is_active':  False,
            'is_staff':   False,
            'email':      'system@internal',
        }
    )
    print('[OK] System user created')


def reverse_system_user(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='system').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('manager', '0020_importhistory_importdetails'),
    ]

    operations = [
        migrations.RunPython(create_system_user, reverse_system_user),
    ]