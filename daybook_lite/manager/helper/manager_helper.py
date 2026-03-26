# manager/activity_helper.py
import logging
from ..models import ActivityLog, Configuration, Ledger, Shop
import requests
from django.db import connection

logger = logging.getLogger(__name__)

def create_shop(short_name, name, d_no, addressline1, addressline2, place, pincode, balance, is_local, ip_address='0.0.0.0', port=0):
    if is_local:
        shop = Shop.objects.create(
            short_name=short_name,
            is_local=True,
            name=name,
            d_no=d_no,
            addressline1=addressline1,
            addressline2=addressline2,
            place=place,
            pincode=pincode,
            balance=balance,
            ip_address=ip_address,
            port=port,
        )
    else:
        # http://127.0.0.1:8000/api/shops/
        response = requests.get(f'http://{ip_address}:{port}/api/shops?short_name={short_name}')
        if response.status_code == 200:
            data = response.json()
            print(f'"API data count: {data}"')
            if len(data) > 0:
                data = data[0]  # Assuming short_name is unique and we get one shop
                shop = Shop.objects.create(
                    id=data['id'],
                    short_name=data['short_name'],
                    is_local=False,
                    name=data['name'],
                    d_no=data['d_no'],
                    addressline1=data['addressline1'],
                    addressline2=data['addressline2'],
                    place=data['place'],
                    pincode=data['pincode'],
                    balance=data['balance'],
                    ip_address=ip_address,
                    port=port,
                )
            else:
                logger.error(f"Shop not available: {data}")
                return None
        print(f"Creating remote shop with IP: {ip_address}, Port: {port}")

    _ensure_entries_shop(shop)
    return shop


def _ensure_entries_shop(shop):
    """Keep old entries_shop table in sync for legacy transactions FK."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM entries_shop WHERE id = ?",
            [shop.id]
        )
        if cursor.fetchone():
            return
        cursor.execute(
            "INSERT INTO entries_shop (id, name, addressline1, addressline2, place, pincode, balance, short_name, d_no) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                shop.id,
                shop.name or '',
                shop.addressline1 or '',
                shop.addressline2 or '',
                shop.place or '',
                shop.pincode,
                shop.balance,
                shop.short_name or '',
                shop.d_no or '',
            ]
        )


def create_ledger(name, license_number, shop):
    try:
        if shop.is_local:
            ledger = Ledger.objects.create(
                name=name,
                license_number=license_number,
                shop=shop
            )
            _ensure_entries_ledger(ledger)
            print(f"Created ledger with ID: {ledger.id} for shop: {shop.short_name}")
        else:
            response = requests.get(f'http://{shop.ip_address}:{shop.port}/api/shops/{shop.id}/ledgers/')
            ledgers = response.json()
            for ledger_data in ledgers:
                ledger = Ledger.objects.create(
                    id=ledger_data['id'],
                    name=ledger_data['name'],
                    license_number=ledger_data['license_number'],
                    shop=shop
                )
                print(f"Created ledger with ID: {ledger.id} for shop: {shop.short_name}")
        return 1    
    except Exception as e:
        logger.error(f"Error creating ledger: {str(e)}", exc_info=True)
        return 0


def _ensure_entries_ledger(ledger):
    """Keep old entries_ledger table synchronized for legacy shop/ledger FKs."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM entries_ledger WHERE id = ?",
            [ledger.id]
        )
        if cursor.fetchone():
            return
        cursor.execute(
            "INSERT INTO entries_ledger (name, shop_id, license_number) VALUES (?, ?, ?)",
            [ledger.name or '', ledger.shop_id, ledger.license_number or '']
        )


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