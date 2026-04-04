# manager/activity_helper.py
import logging
import csv

from django.contrib import messages
from django.conf import settings
from ..models import ActivityLog, Configuration, Ledger, Shop, Group, Type, Accounts
import requests

logger = logging.getLogger(__name__)

def create_shop(short_name, name, d_no, addressline1, addressline2, place, pincode, proprietor, god, pan):
    shop = Shop.objects.create(
            short_name=short_name,
            name=name,
            d_no=d_no,
            addressline1=addressline1,
            addressline2=addressline2,
            place=place,
            pincode=pincode,
            proprietor=proprietor, 
            god=god, 
            pan=pan
        )
    return shop


def create_ledger(name, license_number, shop):
    try:
        ledger = Ledger.objects.create(
            name=name,
            license_number=license_number,
            shop=shop
        )
        print(f"Created ledger with ID: {ledger.id} for shop: {shop.short_name}")
        return 1    
    except Exception as e:
        logger.error(f"Error creating ledger: {str(e)}", exc_info=True)
        return 0


def log_activity(request, action, model_name='', object_id='', description='',shop=None):
    """
    Log a user activity.
    Usage:
        log_activity(request, 'CREATE', 'Loan', loan.id, f'Loan created: {loan.pawn_no}')
    """
    try:
        ip_address = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR')
        )
        ActivityLog.objects.create(
            user        = request.user if request.user.is_authenticated else None,
            action      = action,
            shop        = shop,
            model_name  = model_name,
            object_id   = str(object_id),
            description = description,
            ip_address  = ip_address,
        )
        logger.info(f"Activity logged -> user=[{request.user}] | action=[{action}] | model=[{model_name}] | id=[{object_id}]")
        return True
    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}", exc_info=True)

def purge_log_activities():
    """
    Delete activity logs older than the specified number of days.
    Usage:
        purge_logs(30)  # Deletes logs older than 30 days
    """
    from django.utils import timezone
    older_than_days = int(Configuration.get_value('ACTIVITY_PURGE_DAYS', 30))
    cutoff_date = timezone.now() - timezone.timedelta(days=older_than_days)
    deleted_count, _ = ActivityLog.objects.filter(created_at__lt=cutoff_date).delete()
    logger.info(f"Purged {deleted_count} activity logs older than {older_than_days} days.")
    return 1

def sync_groups_and_types(request,shop_obj):
    groups = [
        [0,'Shop','நம் கடை'],
        [1,'Capital','முதலீடு'],
        [2,'PL','ஆதாயம் '],
        [3,'Purchases','கொள்முதல் '],
        [4,'Liabilities','கடன்'],
        [5,'Miscellaneous','இதர']
    ]

    created_grp = 0
    skipped_grp = 0
    created_type = 0
    skipped_type = 0

    for item in groups:
        # We look up by 'shop' and 'order' (since order is unique)
        group, created = Group.objects.get_or_create(
            order=item[0],
            defaults={
                'e_name': item[1].strip(),
                't_name': item[2].strip()
            }
        )
        
        if created:
            created_grp += 1
        else:
            skipped_grp += 1
    
    csv_file = str(settings.BASE_DIR) + '\\acc_types_groups_mapping.csv'
    print(csv_file)
    with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
        # Create a reader object that iterates over the lines of the file
        csv_reader = csv.reader(file)

        for row in csv_reader:
            acc_type, created = Type.objects.get_or_create(
                shop = shop_obj,
                e_name = row[2].strip(),
                defaults={
                    't_name':row[1].strip(),
                    'group':Group.objects.get(order=row[0])
                }
            )

            if created:
                created_type += 1
            else:
                print(f'{acc_type.e_name} is already mapped to {acc_type.group.e_name} ')
                skipped_type += 1

    logger.info(f'For {shop_obj.short_name}, {str(created_grp)} groups created & {str(skipped_grp)} groups skipped, since its already exists')
    logger.info(f'For {shop_obj.short_name}, {str(created_type)} types created & {str(skipped_type)} types skipped, since its already exists')
    messages.info(request, f'Total {created_grp} groups created & {skipped_grp} groups skipped, and {created_type} types created & {skipped_type} types skipped.')
    return True

def update_account_priority(account, increment=1):
    try:
        # Get the current maximum priority for the shop
        account = Accounts.objects.get(pk=account.id)
        account.priority += increment
        account.save()
        logger.info(f"Updated priority for account ID {account.id} to {account.priority}")
    except Exception as e:
        logger.error(f"Error updating account priority: {str(e)}", exc_info=True)