# manager/activity_helper.py
import logging
from ..models import ActivityLog, Configuration, Ledger, Shop
import requests

logger = logging.getLogger(__name__)

def create_shop(short_name, name, d_no, addressline1, addressline2, place, pincode, balance):
    shop = Shop.objects.create(
            short_name=short_name,
            name=name,
            d_no=d_no,
            addressline1=addressline1,
            addressline2=addressline2,
            place=place,
            pincode=pincode,
            balance=balance,
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


def log_activity(request, action, model_name='', object_id='', description=''):
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
            model_name  = model_name,
            object_id   = str(object_id),
            description = description,
            ip_address  = ip_address,
        )
        logger.info(f"Activity logged -> user=[{request.user}] | action=[{action}] | model=[{model_name}] | id=[{object_id}]")
        return purge_log_activities()  # Call purge after logging new activity
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