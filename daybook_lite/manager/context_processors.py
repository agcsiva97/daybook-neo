from django.conf import settings
from .models import Shop, Configuration

def app_version(request):
    return {"app_version": settings.APP_VERSION}

# def app_globals(request):
#     from .models import ActivityLog

#     current_shop = None
#     last_sync = None
#     financial_year_display = None

#     if request.user.is_authenticated:
#         # Pull the active shop from the session (set it when user picks a shop)
#         default_shop_short_name = Configuration.objects.filter(key=Configuration.Key.DEFAULT_SHOP).first()
#         print(default_shop_short_name.value)
#         if default_shop_short_name:
#             current_shop = Shop.objects.filter(short_name=default_shop_short_name.value).first()

#         # Last sync time — pull from ActivityLog or a Configuration key
#         last_sync = current_shop.last_transaction_imported_at
#         # ActivityLog.objects.filter(
#         #    action="sync_export"
#         #).order_by("-created_at").values_list("created_at", flat=True).first()

#         # Indian FY: April–March
#         from django.utils import timezone
#         today = timezone.localdate()
#         print(today)
#         fy_start = today.year if today.month >= 4 else today.year - 1
#         financial_year_display = f"{fy_start} – {str(fy_start + 1)[-2:]}"

#     return {
#         "app_version": settings.APP_VERSION,
#         "current_shop": current_shop,
#         "last_sync": last_sync,
#         "financial_year_display": financial_year_display,
#     }