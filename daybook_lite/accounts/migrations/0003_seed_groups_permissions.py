from django.db import migrations
from django.db.models.signals import post_migrate
from django.apps import apps as django_apps


def seed_groups_permissions(apps, schema_editor):
    from django.contrib.auth.models import Group, Permission

    def do_seed(sender, app_config, **kwargs):
        # Only run once, after the last app finishes migrating
        if app_config.name != 'manager':
            return

        groups_data = {
            'Admin': [
                # Manager
                'add_user', 'change_user', 'delete_user', 'view_user',
                'change_shop', 'delete_shop', 'view_shop',
                'add_ledger', 'change_ledger', 'delete_ledger', 'view_ledger',
                'change_configuration', 'delete_configuration', 'view_configuration',
                'view_activitylog',
                # entries
                'add_transactions', 'change_transactions', 'delete_transactions', 'view_transactions',
                'add_loan', 'change_loan', 'delete_loan', 'view_loan',
                'add_denomination', 'change_denomination', 'delete_denomination', 'view_denomination',
                'add_historicaltransactions', 'change_historicaltransactions', 'delete_historicaltransactions', 'view_historicaltransactions',
                'add_historicalloan', 'change_historicalloan', 'delete_historicalloan', 'view_historicalloan',
            ],
            'Staff': [
                'add_transactions', 'change_transactions', 'view_transactions',
                'add_denomination', 'change_denomination', 'view_denomination',
                'add_loan', 'change_loan', 'view_loan',
            ],
            'Super Admin': [
                # auth
                'add_user', 'change_user', 'delete_user', 'view_user',
                'add_group', 'change_group', 'delete_group', 'view_group',
                'add_permission', 'change_permission', 'delete_permission', 'view_permission',
                'add_logentry', 'change_logentry', 'delete_logentry', 'view_logentry',
                'add_contenttype', 'change_contenttype', 'delete_contenttype', 'view_contenttype',
                # entries
                'add_transactions', 'change_transactions', 'delete_transactions', 'view_transactions',
                'add_loan', 'change_loan', 'delete_loan', 'view_loan',
                'add_denomination', 'change_denomination', 'delete_denomination', 'view_denomination',
                'add_historicaltransactions', 'change_historicaltransactions', 'delete_historicaltransactions', 'view_historicaltransactions',
                'add_historicalloan', 'change_historicalloan', 'delete_historicalloan', 'view_historicalloan',
                # manager
                'add_shop', 'change_shop', 'delete_shop', 'view_shop',
                'add_ledger', 'change_ledger', 'delete_ledger', 'view_ledger',
                'add_configuration', 'change_configuration', 'delete_configuration', 'view_configuration',
                'add_activitylog', 'change_activitylog', 'delete_activitylog', 'view_activitylog',
            ],
        }

        for group_name, codenames in groups_data.items():
            group, created = Group.objects.get_or_create(name=group_name)
            group.permissions.clear()  # avoid duplicates on re-run
            for codename in codenames:
                perms = Permission.objects.filter(codename=codename)
                for perm in perms:
                    group.permissions.add(perm)
            print(f'[OK] {"Created" if created else "Updated"}: {group_name} -> {group.permissions.count()} permissions')

    post_migrate.connect(do_seed, weak=False)


def reverse_seed(apps, schema_editor):
    from django.contrib.auth.models import Group
    Group.objects.filter(name__in=['Admin', 'Staff', 'Super Admin']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_alternate_number_user_mobile_number'),
        ('entries', '0026_remove_shop_ledger'),
        ('manager', '0011_remove_shop_ip_address_remove_shop_is_local_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(seed_groups_permissions, reverse_seed),
    ]