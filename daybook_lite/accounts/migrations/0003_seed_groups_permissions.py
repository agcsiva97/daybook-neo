from django.db import migrations


def seed_groups_permissions(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    groups_data = {
        'Admin': [
            'change_user',       # ← was change_account
            'view_user',         # ← was view_account
            'add_transactions', 'change_transactions', 'delete_transactions', 'view_transactions',
        ],
        'Staff': [
            'add_transactions', 'change_transactions', 'view_transactions',
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
        group, _ = Group.objects.get_or_create(name=group_name)
        for codename in codenames:
            perms = Permission.objects.filter(codename=codename)
            if not perms.exists():
                print(f'[WARN] Permission not found: {codename}')
            for perm in perms:
                group.permissions.add(perm)


def reverse_seed(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
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