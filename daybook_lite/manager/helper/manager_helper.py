# manager/activity_helper.py
from django.utils import timezone
import logging
import csv
import requests

from django.contrib import messages
from django.conf import settings
from ..models import ActivityLog, Configuration, Ledger, Shop, Type, Accounts
import requests

from entries.models import GLDSLRPriceHistory

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

def sync_types(request,shop_obj):
        
    csv_file = str(settings.BASE_DIR) + '\\acc_types_groups_mapping.csv'
    print(csv_file)
    skipped_type, created_type = 0, 0
    with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
        # Create a reader object that iterates over the lines of the file
        csv_reader = csv.reader(file)

        for row in csv_reader:
            acc_type, created = Type.objects.update_or_create(
                shop = shop_obj,
                e_name = row[2].strip(),
                defaults={
                    't_name':row[1].strip(),
                    'group_order':row[0].strip()
                }
            )

            if created:
                created_type += 1
            else:
                print(f'{acc_type.e_name} is already mapped to group order {acc_type.group_order} ')
                skipped_type += 1

    logger.info(f'For {shop_obj.short_name}, {str(created_type)} types created & {str(skipped_type)} types skipped, since its already exists')
    messages.info(request, f'{created_type} Types created & {skipped_type} types skipped.')
    return True

def get_groups():
    groups = [
        [0,'Shop','நம் கடை'],
        [1,'Capital','மூலதனம்'],
        [2,'PL','ஆதாயம் '],
        [3,'Purchases','கொள்முதல் '],
        [4,'Liabilities','கடன்'],
        [5,'Miscellaneous','இதர']
    ]
    return groups

def get_group(order):
    groups = [
        [0,'Shop','நம் கடை'],
        [1,'Capital','மூலதனம்'],
        [2,'PL','ஆதாயம் '],
        [3,'Purchases','கொள்முதல் '],
        [4,'Liabilities','கடன்'],
        [5,'Miscellaneous','இதர']
    ]
    return groups[order] if 0 <= order < len(groups) else None

def update_account_priority(account, increment=1):
    try:
        # Get the current maximum priority for the shop
        account = Accounts.objects.get(pk=account.id)
        account.priority += increment
        account.save()
        logger.info(f"Updated priority for account ID {account.id} to {account.priority}")
    except Exception as e:
        logger.error(f"Error updating account priority: {str(e)}", exc_info=True)

def get_gold_price():
    try:
        latest_price = GLDSLRPriceHistory.objects.filter(type='Gold').latest()
        return {'price': latest_price.price, 'updated_at': latest_price.updated_at}
    except GLDSLRPriceHistory.DoesNotExist:
        logger.warning("No gold price history found.")
        return None
    except Exception as e:
        logger.error(f"Error fetching gold price: {str(e)}", exc_info=True)
        return None
    
def get_silver_price():
    try:
        latest_price = GLDSLRPriceHistory.objects.filter(type='Silver').latest()
        return {'price': latest_price.price, 'updated_at': latest_price.updated_at}
    except GLDSLRPriceHistory.DoesNotExist:
        logger.warning("No silver price history found.")
        return None
    except Exception as e:
        logger.error(f"Error fetching silver price: {str(e)}", exc_info=True)
        return None

def get_live_price(item):
    try:
        metal = {'gold':'XAU','silver':'XAG'}
        response = requests.get(f"https://api.gold-api.com/price/{metal[item]}/INR")
        if response.status_code == 200:
            result = response.json()
            new_price = round(result.get('price'), 2)
            print(f"Fetched {item} price: {new_price} INR")
            new_price = round((new_price / 31.1035), 2)
            print(f"Converted {item} price to /g: {new_price} INR")
            new_price = round(new_price + (new_price * .10), 2)
            print(f"{item.capitalize()} price after adding import duty: {new_price} INR")
            new_price = round(new_price, 2)
            print(f"{item.capitalize()} price: {new_price} INR")    
        return new_price
    except Exception as e:
        logger.error(f"Error fetching live price for {item}: {str(e)}", exc_info=True)
        return None

def update_gold_price():
    try:
        new_price = get_live_price('gold')
        if new_price is not None:
            try:
                latest_price = GLDSLRPriceHistory.objects.filter(type='Gold').latest()
                if latest_price.created_at.date() == timezone.now().date():
                    latest_price.price = new_price
                    latest_price.save()
                    logger.info(f"Updated existing gold price to {new_price}")
                else:
                    GLDSLRPriceHistory.objects.create(
                        price=new_price, type='Gold'
                        )
                    logger.info(f"Updated gold price to {new_price}")
            except GLDSLRPriceHistory.DoesNotExist:
                GLDSLRPriceHistory.objects.create(price=new_price, type='Gold')
                logger.info(f"Created first gold price entry: {new_price}")
                return True
            return True
        else:
            logger.error("Error fetching gold price: Unable to retrieve live price")
            return False
    except Exception as e:
        logger.error(f"Error updating gold price: {str(e)}", exc_info=True)
        return False
    
def update_silver_price():
    try:
        new_price = get_live_price('silver')
        if new_price is not None:
            try:
                latest_price = GLDSLRPriceHistory.objects.filter(type='Silver').latest()
                if latest_price.created_at.date() == timezone.now().date():
                    latest_price.price = new_price
                    latest_price.save()
                    logger.info(f"Updated existing silver price to {new_price}")
                else:
                    GLDSLRPriceHistory.objects.create(
                        price=new_price, type='Silver'
                        )
                    logger.info(f"Updated silver price to {new_price}")
            except GLDSLRPriceHistory.DoesNotExist:
                GLDSLRPriceHistory.objects.create(price=new_price, type='Silver')
                logger.info(f"Created first silver price entry: {new_price}")
                return True
            return True
        else:
            logger.error("Error fetching silver price: Unable to retrieve live price")
            return False
    except Exception as e:
        logger.error(f"Error updating silver price: {str(e)}", exc_info=True)
        return False