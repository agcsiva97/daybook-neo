from datetime import datetime
import json
import logging
from pyexpat.errors import messages
from decimal import Decimal, ROUND_HALF_UP


from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q, Sum 
from django.http import JsonResponse

from .helper import manager_helper, date_helper
from .forms import LedgerForm, ShopForm, ShopEditForm, AccountsForm, AccountsEditForm
from django.core.paginator import Paginator
from django.contrib.auth import  get_user_model

from entries.views import admin_required, super_admin_required, is_admin
from .models import Configuration, Shop, ActivityLog, Ledger, Accounts, Type, Group, ExportHistory, ImportHistory, ExportDetails, ImportDetails
from entries.models import Transactions, Loan
from entries.helpers import transactions as transaction_helper

logger = logging.getLogger(__name__)
User = get_user_model()

# Create your views here.
@login_required
@admin_required
def dashboard(request):
    shops = Shop.objects.all().order_by('short_name')
    return render(request, 'manager/dashboard.html', {'nav_title': 'Dashboard', 'shops': shops, 'app_name': 'manager', 'is_super_admin': request.user.is_superuser})

@login_required
@admin_required
def shops_list(request):
    temp_shops = Shop.objects.all().order_by('short_name')
    ledgers = Ledger.objects.all().order_by('name')
    shops = []
    for shop in temp_shops:
        shops.append({
            'id':           shop.id,
            'short_name':   shop.short_name,
            'name':         shop.name,
            'd_no':         shop.d_no,
            'addressline1': shop.addressline1,
            'addressline2': shop.addressline2,
            'place':        shop.place,
            'pincode':      shop.pincode,
            'ledgers':      shop.ledgers.all(),
            'cur_balance':  transaction_helper.get_balance(shop),
        })
    return render(request, 'manager/shops_list.html', {
        'nav_title': 'Shops', 
        'shops': shops,
        'ledgers': ledgers,
        'is_super_admin': request.user.is_superuser,
        'app_name': 'manager',
        })

@login_required
@admin_required
def sync_history(request):
    """Display export and import history for all shops in a unified table"""
    # Fetch all export history
    exports = ExportHistory.objects.select_related('shop').order_by('-exported_at')
    
    # Fetch all import history
    imports = ImportHistory.objects.select_related('shop').order_by('-imported_at')
    
    # Combine and sort by date (most recent first)
    sync_events = []
    
    for export in exports:
        sync_events.append({
            'type': 'Export',
            'type_label': 'Export',
            'id': export.id,
            'shop_id': export.shop.id,
            'shop_name': export.shop.short_name,
            'shop_full_name': export.shop.name,
            'data_type': export.export_type.capitalize(),
            'timestamp': export.exported_at,
            'icon': 'fa-arrow-up-from-bracket',
            'badge_class': 'bg-success',
        })
    
    for import_record in imports:
        sync_events.append({
            'type': 'Import',
            'type_label': 'Import',
            'id': import_record.id,
            'shop_id': import_record.shop.id,
            'shop_name': import_record.shop.short_name,
            'shop_full_name': import_record.shop.name,
            'data_type': import_record.import_type.capitalize(),
            'timestamp': import_record.imported_at,
            'icon': 'fa-arrow-down-to-bracket',
            'badge_class': 'bg-info',
        })
    
    # Sort by timestamp (most recent first)
    sync_events.sort(key=lambda x: x['timestamp'], reverse=True)

    shops = Shop.objects.all().order_by('short_name')
    
    return render(request, 'manager/sync_history.html', {
        'nav_title': 'Sync History',
        'sync_events': sync_events,
        'shops': shops,
        'total_events': len(sync_events),
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })


@login_required
@admin_required
def export_details(request, export_id):
    """View details of a specific export"""
    export_history = get_object_or_404(ExportHistory, pk=export_id)
    export_details_qs = ExportDetails.objects.filter(export_history=export_history).order_by('record_type', 'record_id')
    
    # Group by record type
    details_by_type = {}
    for detail in export_details_qs:
        if detail.record_type not in details_by_type:
            details_by_type[detail.record_type] = []
        details_by_type[detail.record_type].append(detail)
    
    context = {
        'nav_title': 'Export Details',
        'export_history': export_history,
        'details_by_type': details_by_type,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'manager/export_details.html', context)


@login_required
@admin_required
def import_details(request, import_id):
    """View details of a specific import"""
    import_history = get_object_or_404(ImportHistory, pk=import_id)
    import_details_qs = ImportDetails.objects.filter(import_history=import_history).order_by('record_type', 'record_id')
    
    # Group by record type
    details_by_type = {}
    for detail in import_details_qs:
        if detail.record_type not in details_by_type:
            details_by_type[detail.record_type] = []
        details_by_type[detail.record_type].append(detail)
    
    context = {
        'nav_title': 'Import Details',
        'import_history': import_history,
        'details_by_type': details_by_type,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'manager/import_details.html', context)

def import_shop(request):
    """Import shop, ledgers, types, and accounts from JSON file"""
    if request.method == 'POST' and request.FILES.get('json_file'):
        try:
            json_file = request.FILES['json_file']
            import_data = json.load(json_file)
            
            with db_transaction.atomic():
                # Import Shop
                shop_data = import_data.get('shop', {})
                shop_id = shop_data.get('id', '').strip()
                
                if not shop_id:  # Create new shop if ID is empty
                    shop = Shop.objects.create(
                        short_name=shop_data.get('short_name', 'shop'),
                        name=shop_data.get('name', ''),
                        proprietor=shop_data.get('proprietor', ''),
                        god=shop_data.get('god', ''),
                        pan=shop_data.get('pan', ''),
                        d_no=shop_data.get('d_no', ''),
                        addressline1=shop_data.get('addressline1', ''),
                        addressline2=shop_data.get('addressline2', ''),
                        place=shop_data.get('place', ''),
                        pincode=shop_data.get('pincode', ''),
                    )
                    shop_status = 'created'
                else:
                    # Try to update existing shop or create new one
                    shop, created = Shop.objects.update_or_create(
                        id=shop_id,
                        defaults={
                            'short_name': shop_data.get('short_name', 'shop'),
                            'name': shop_data.get('name', ''),
                            'proprietor': shop_data.get('proprietor', ''),
                            'god': shop_data.get('god', ''),
                            'pan': shop_data.get('pan', ''),
                            'd_no': shop_data.get('d_no', ''),
                            'addressline1': shop_data.get('addressline1', ''),
                            'addressline2': shop_data.get('addressline2', ''),
                            'place': shop_data.get('place', ''),
                            'pincode': shop_data.get('pincode', ''),
                        }
                    )
                    shop_status = 'created' if created else 'updated'
                
                logger.info(f"Shop {shop_status}: {shop.id}")
                
                # Import Ledgers
                ledger_count = 0
                for ledger_data in import_data.get('ledgers', []):
                    ledger_id = ledger_data.get('id', '').strip()
                    
                    if not ledger_id:
                        ledger = Ledger.objects.create(
                            name=ledger_data.get('name', ''),
                            license_number=ledger_data.get('license_number', ''),
                            shop=shop
                        )
                    else:
                        ledger, created = Ledger.objects.update_or_create(
                            id=ledger_id,
                            defaults={
                                'name': ledger_data.get('name', ''),
                                'license_number': ledger_data.get('license_number', ''),
                                'shop': shop
                            }
                        )
                    ledger_count += 1
                
                # Import Types
                type_count = 0
                for type_data in import_data.get('types', []):
                    type_id = type_data.get('id', '').strip()
                    group_id = type_data.get('group_id')
                    
                    try:
                        group = Group.objects.get(id=group_id) if group_id else None
                    except Group.DoesNotExist:
                        group = None
                    
                    if not type_id:
                        type_obj = Type.objects.create(
                            e_name=type_data.get('e_name', ''),
                            t_name=type_data.get('t_name', ''),
                            shop=shop,
                            group=group
                        )
                    else:
                        type_obj, created = Type.objects.update_or_create(
                            id=type_id,
                            defaults={
                                'e_name': type_data.get('e_name', ''),
                                't_name': type_data.get('t_name', ''),
                                'shop': shop,
                                'group': group
                            }
                        )
                    type_count += 1
                
                # Import Accounts
                account_count = 0
                for account_data in import_data.get('accounts', []):
                    account_id = account_data.get('id', '').strip()
                    acc_type_id = account_data.get('acc_type_id')
                    
                    try:
                        acc_type = Type.objects.get(id=acc_type_id) if acc_type_id else None
                    except Type.DoesNotExist:
                        acc_type = None
                    
                    if not account_id:
                        account = Accounts.objects.create(
                            e_name=account_data.get('e_name', ''),
                            t_name=account_data.get('t_name', ''),
                            shop=shop,
                            acc_type=acc_type,
                            priority=account_data.get('priority', 0),
                            is_admin_only=account_data.get('is_admin_only', False)
                        )
                    else:
                        account, created = Accounts.objects.update_or_create(
                            id=account_id,
                            defaults={
                                'e_name': account_data.get('e_name', ''),
                                't_name': account_data.get('t_name', ''),
                                'shop': shop,
                                'acc_type': acc_type,
                                'priority': account_data.get('priority', 0),
                                'is_admin_only': account_data.get('is_admin_only', False)
                            }
                        )
                    account_count += 1
                
                # Update last import timestamp
                shop.last_transaction_imported_at = timezone.now()
                shop.save(update_fields=['last_transaction_imported_at'])
                
                # Create import history record
                ImportHistory.objects.create(shop=shop, import_type='shop')
                
                messages.success(request, f'Shop imported successfully! Shop: {shop.short_name}, Ledgers: {ledger_count}, Types: {type_count}, Accounts: {account_count}')
                logger.info(f"Shop import completed: {shop.id} - Ledgers: {ledger_count}, Types: {type_count}, Accounts: {account_count}")
                return redirect('manager:shops_list')
                
        except json.JSONDecodeError:
            messages.error(request, 'Invalid JSON file. Please upload a valid JSON file.')
            logger.error("JSON decode error during shop import", exc_info=True)
        except Exception as e:
            messages.error(request, f'Error importing shop: {str(e)}')
            logger.error(f"Error importing shop: {str(e)}", exc_info=True)
    
    return redirect('manager:shops_list')

@login_required
@super_admin_required
def add_shop(request):
    if request.method == 'POST':
        form = ShopForm(request.POST)
        if form.is_valid():
            # print(f"is local: {request.POST.get('is_local')}")
            short_name = form.cleaned_data.get('short_name')
            name = form.cleaned_data.get('name')
            d_no = form.cleaned_data.get('d_no')
            addressline1 = form.cleaned_data.get('addressline1')
            addressline2 = form.cleaned_data.get('addressline2')
            place = form.cleaned_data.get('place')
            pincode = form.cleaned_data.get('pincode')
            god = form.cleaned_data.get('god')
            pan = form.cleaned_data.get('pan')
            proprietor = form.cleaned_data.get('proprietor')
            # balance = form.cleaned_data.get('balance')
            try:
                with db_transaction.atomic():
                    shop = manager_helper.create_shop(short_name, name, d_no, addressline1, addressline2, place, pincode, proprietor, god, pan)
                    if shop is not None:
                        print(f"Shop created with ID: {shop.id}")
                        manager_helper.create_ledger(shop.short_name, "", shop)
                        # logger.info(f"Shop created by {request.user.username}: {shop.id}")
                        messages.success(request, f'Shop "{shop.short_name}" created successfully!')
                        manager_helper.sync_groups_and_types(request, shop)
                        return redirect('manager:home')
            except Exception as e:
                logger.error(f"Error creating shop by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, f'Error creating shop: {str(e)}')
        else:
            logger.warning(f"Shop form validation failed: {form.errors}")
    else:
        form = ShopForm()
    
    return render(request, 'manager/add_shop.html', {
        'nav_title': 'Shops',
        'form': form,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
    })


@login_required
@admin_required
def shop_info(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    ledgers = Ledger.objects.filter(shop=shop).order_by('name')
    balance = transaction_helper.get_balance(shop)  # Calculate balance from transactions for accuracy
    
    # Get all transactions for this shop
    accounts_list = Accounts.objects.filter(shop=shop)
    for account in accounts_list:
        account.balance = transaction_helper.get_account_balance(account)  # Add balance attribute to each account
    
    
    return render(request, 'manager/shop_info.html', {
        'nav_title': 'Shops',
        'shop': shop,
        'ledgers': ledgers,
        'accounts_list': accounts_list,
        'balance': balance,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'app_name': 'manager',
    })


@login_required
@admin_required
def export_shop(request, pk):
    """Export shop with related ledgers, accounts, and types as JSON"""
    try:
        shop = get_object_or_404(Shop, pk=pk)
        
        # Prepare shop data
        shop_data = {
            'id': shop.id,
            'short_name': shop.short_name,
            'name': shop.name,
            'proprietor': shop.proprietor or '',
            'god': shop.god or '',
            'pan': shop.pan or '',
            'd_no': shop.d_no or '',
            'addressline1': shop.addressline1 or '',
            'addressline2': shop.addressline2 or '',
            'place': shop.place or '',
            'pincode': str(shop.pincode) if shop.pincode else '',
        }
        
        # Get related ledgers
        ledgers_data = []
        for ledger in shop.ledgers.all():
            ledgers_data.append({
                'id': ledger.id,
                'name': ledger.name,
                'license_number': ledger.license_number or '',
                'shop_id': ledger.shop_id,
            })
        
        # Get related types
        types_data = []
        for type_obj in shop.types.all():
            types_data.append({
                'id': type_obj.id,
                'e_name': type_obj.e_name or '',
                't_name': type_obj.t_name or '',
                'shop_id': type_obj.shop_id,
                'group_id': type_obj.group_id,
            })
        
        # Get related accounts
        accounts_data = []
        for account in shop.shop_accounts.all():
            accounts_data.append({
                'id': account.id,
                'e_name': account.e_name or '',
                't_name': account.t_name or '',
                'shop_id': account.shop_id,
                'acc_type_id': account.acc_type_id,
                'priority': account.priority,
                'is_admin_only': account.is_admin_only,
            })
        
        # Build export data
        export_data = {
            'shop': shop_data,
            'ledgers': ledgers_data,
            'types': types_data,
            'accounts': accounts_data,
            'export_date': timezone.now().isoformat(),
        }
        
        # Return JSON with download headers
        from django.http import HttpResponse
        
        # Create export history record
        ExportHistory.objects.create(shop=shop, export_type='shop')
        
        response = HttpResponse(
            json.dumps(export_data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="shop_{shop.short_name}_export.json"'
        return response
        
    except Exception as e:
        logger.error(f"Error exporting shop {pk}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Error exporting shop: {str(e)}'}, status=500)


@login_required
@admin_required
def export_transactions(request, pk):
    """Export shop transactions, types, and accounts as JSON with multiple filtering options"""
    if request.method == 'POST':
        try:
            shop = get_object_or_404(Shop, pk=pk)
            export_mode = request.POST.get('export_type', 'all')
            
            # Capture current time for use in timestamp updates
            current_export_time = timezone.now()
            
            export_data = {
                'shop_id': shop.id,
                'shop_name': shop.name,
                'export_mode': export_mode,
                'export_date': current_export_time.isoformat(),
            }
            
            if export_mode == 'all':
                # Export ALL: types, accounts, transactions with all columns including id
                
                # Get all types associated with shop
                types_qs = Type.objects.filter(shop=shop).order_by('id')
                types_data = []
                for type_obj in types_qs:
                    types_data.append({
                        'id': type_obj.id,
                        'e_name': type_obj.e_name or '',
                        't_name': type_obj.t_name or '',
                        'shop_id': type_obj.shop_id,
                        'group_id': type_obj.group_id,
                    })
                
                # Get all accounts associated with shop
                accounts_qs = Accounts.objects.filter(shop=shop).order_by('id')
                accounts_data = []
                for account in accounts_qs:
                    accounts_data.append({
                        'id': account.id,
                        'e_name': account.e_name or '',
                        't_name': account.t_name or '',
                        'shop_id': account.shop_id,
                        'acc_type_id': account.acc_type_id,
                        'priority': account.priority,
                        'is_admin_only': account.is_admin_only,
                    })
                
                # Get all transactions associated with shop
                transactions_qs = Transactions.objects.filter(shop=shop).select_related('acc').order_by('transaction_dt')
                transactions_data = []
                for trans in transactions_qs:
                    transactions_data.append({
                        'id': trans.id,
                        'shop_id': trans.shop_id,
                        'account_id': trans.acc_id,
                        'account_name': trans.acc.t_name if trans.acc else '',
                        'transaction_dt': trans.transaction_dt.isoformat(),
                        'amount': str(trans.amount),
                        'tr_type': trans.tr_type,
                        'remarks': trans.remarks or '',
                        'name': trans.name or '',
                        'is_tally': trans.is_tally,
                        'created_at': trans.created_at.isoformat(),
                        'updated_at': trans.updated_at.isoformat() if trans.updated_at else '',
                        'created_by': trans.created_by.username if trans.created_by else '',
                        'updated_by': trans.updated_by.username if trans.updated_by else '',
                    })
                
                export_data.update({
                    'types_count': len(types_data),
                    'types': types_data,
                    'accounts_count': len(accounts_data),
                    'accounts': accounts_data,
                    'transactions_count': len(transactions_data),
                    'transactions': transactions_data,
                })
                
            elif export_mode == 'date_range':
                # Export transactions for date range
                from_date = request.POST.get('from_date')
                to_date = request.POST.get('to_date')
                
                if not from_date or not to_date:
                    return JsonResponse({'error': 'Date range is required for date range export'}, status=400)
                
                from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
                to_dt = datetime.strptime(to_date, '%Y-%m-%d').date()
                
                transactions_qs = Transactions.objects.filter(
                    shop=shop,
                    transaction_dt__date__range=[from_dt, to_dt]
                ).select_related('acc').order_by('transaction_dt')
                
                transactions_data = []
                for trans in transactions_qs:
                    transactions_data.append({
                        'id': trans.id,
                        'shop_id': trans.shop_id,
                        'account_id': trans.acc_id,
                        'account_name': trans.acc.t_name if trans.acc else '',
                        'transaction_dt': trans.transaction_dt.isoformat(),
                        'amount': str(trans.amount),
                        'tr_type': trans.tr_type,
                        'remarks': trans.remarks or '',
                        'name': trans.name or '',
                        'is_tally': trans.is_tally,
                        'created_at': trans.created_at.isoformat(),
                        'updated_at': trans.updated_at.isoformat() if trans.updated_at else '',
                        'created_by': trans.created_by.username if trans.created_by else '',
                        'updated_by': trans.updated_by.username if trans.updated_by else '',
                    })
                
                export_data.update({
                    'date_from': from_date,
                    'date_to': to_date,
                    'transactions_count': len(transactions_data),
                    'transactions': transactions_data,
                })
                
            elif export_mode == 'after_last_export':
                # Export changes since last export using activity log
                last_export_time = shop.last_transaction_exported_at
                
                # If no last export exists, fetch all activity logs for the shop
                if last_export_time is None:
                    activity_logs = ActivityLog.objects.filter(
                        shop=shop,
                        model_name__in=['Type', 'Accounts', 'Transaction'],
                        action__in=['CREATE', 'UPDATE', 'DELETE']
                    ).order_by('created_at')
                else:
                    # Get activity logs after last export for relevant models
                    # Use __gte (>=) instead of __gt (>) to include logs at the exact export timestamp
                    # and catch any records that might have been created at the boundary
                    activity_logs = ActivityLog.objects.filter(
                        shop=shop,
                        created_at__gte=last_export_time,
                        model_name__in=['Type', 'Accounts', 'Transaction'],
                        action__in=['CREATE', 'UPDATE', 'DELETE']
                    ).order_by('created_at')
                
                # Process activity logs and collect changes by entity type and action
                types_created = []
                types_updated = []
                types_deleted = []
                accounts_created = []
                accounts_updated = []
                accounts_deleted = []
                transactions_created = []
                transactions_updated = []
                transactions_deleted = []
                
                for log in activity_logs:
                    try:
                        if log.model_name.lower() == 'type':
                            if log.action == 'CREATE':
                                # Record was created, try to get current state
                                try:
                                    type_obj = Type.objects.get(id=log.object_id, shop=shop)
                                    types_created.append({
                                        'id': type_obj.id,
                                        'e_name': type_obj.e_name or '',
                                        't_name': type_obj.t_name or '',
                                        'shop_id': type_obj.shop_id,
                                        'group_id': type_obj.group_id,
                                    })
                                except Type.DoesNotExist:
                                    pass
                            elif log.action == 'UPDATE':
                                try:
                                    type_obj = Type.objects.get(id=log.object_id, shop=shop)
                                    types_updated.append({
                                        'id': type_obj.id,
                                        'e_name': type_obj.e_name or '',
                                        't_name': type_obj.t_name or '',
                                        'shop_id': type_obj.shop_id,
                                        'group_id': type_obj.group_id,
                                    })
                                except Type.DoesNotExist:
                                    pass
                            elif log.action == 'DELETE':
                                types_deleted.append({
                                    'id': log.object_id,
                                    'description': log.description,
                                    'deleted_at': log.created_at.isoformat(),
                                })
                                
                        elif log.model_name.lower() == 'accounts':
                            if log.action == 'CREATE':
                                try:
                                    account = Accounts.objects.get(id=log.object_id, shop=shop)
                                    accounts_created.append({
                                        'id': account.id,
                                        'e_name': account.e_name or '',
                                        't_name': account.t_name or '',
                                        'shop_id': account.shop_id,
                                        'acc_type_id': account.acc_type_id,
                                        'priority': account.priority,
                                        'is_admin_only': account.is_admin_only,
                                    })
                                except Accounts.DoesNotExist:
                                    pass
                            elif log.action == 'UPDATE':
                                try:
                                    account = Accounts.objects.get(id=log.object_id, shop=shop)
                                    accounts_updated.append({
                                        'id': account.id,
                                        'e_name': account.e_name or '',
                                        't_name': account.t_name or '',
                                        'shop_id': account.shop_id,
                                        'acc_type_id': account.acc_type_id,
                                        'priority': account.priority,
                                        'is_admin_only': account.is_admin_only,
                                    })
                                except Accounts.DoesNotExist:
                                    pass
                            elif log.action == 'DELETE':
                                accounts_deleted.append({
                                    'id': log.object_id,
                                    'description': log.description,
                                    'deleted_at': log.created_at.isoformat(),
                                })
                                
                        elif log.model_name.lower() == 'transaction':
                            if log.action == 'CREATE':
                                try:
                                    print(f"Processing CREATE log for transaction ID: {log.object_id}")
                                    trans = Transactions.objects.get(id=log.object_id)
                                    transactions_created.append({
                                        'id': trans.id,
                                        'shop_id': trans.shop_id,
                                        'account_id': trans.acc_id,
                                        'account_name': trans.acc.t_name if trans.acc else '',
                                        'transaction_dt': trans.transaction_dt.isoformat(),
                                        'amount': str(trans.amount),
                                        'tr_type': trans.tr_type,
                                        'remarks': trans.remarks or '',
                                        'name': trans.name or '',
                                        'is_tally': trans.is_tally,
                                        'created_at': trans.created_at.isoformat(),
                                        'created_by': trans.created_by.username if trans.created_by else '',
                                    })
                                except Transactions.DoesNotExist:
                                    pass
                            elif log.action == 'UPDATE':
                                try:
                                    trans = Transactions.objects.get(id=log.object_id)
                                    transactions_updated.append({
                                        'id': trans.id,
                                        'shop_id': trans.shop_id,
                                        'account_id': trans.acc_id,
                                        'account_name': trans.acc.t_name if trans.acc else '',
                                        'transaction_dt': trans.transaction_dt.isoformat(),
                                        'amount': str(trans.amount),
                                        'tr_type': trans.tr_type,
                                        'remarks': trans.remarks or '',
                                        'name': trans.name or '',
                                        'is_tally': trans.is_tally,
                                        'updated_at': trans.updated_at.isoformat() if trans.updated_at else '',
                                        'updated_by': trans.updated_by.username if trans.updated_by else '',
                                    })
                                except Transactions.DoesNotExist:
                                    pass
                            elif log.action == 'DELETE':
                                transactions_deleted.append({
                                    'id': log.object_id,
                                    'description': log.description,
                                    'deleted_at': log.created_at.isoformat(),
                                })
                    except Exception as e:
                        logger.warning(f"Error processing activity log {log.id}: {str(e)}")
                        continue
                
                export_data.update({
                    'last_export_time': last_export_time.isoformat() if last_export_time else None,
                    'types': {
                        'created': types_created,
                        'updated': types_updated,
                        'deleted': types_deleted,
                    },
                    'accounts': {
                        'created': accounts_created,
                        'updated': accounts_updated,
                        'deleted': accounts_deleted,
                    },
                    'transactions': {
                        'created': transactions_created,
                        'updated': transactions_updated,
                        'deleted': transactions_deleted,
                    },
                })
            
            # Update last export timestamp (use the time captured at the start for consistency)
            if export_mode == 'after_last_export':
                shop.last_transaction_exported_at = current_export_time
            else:
                shop.last_transaction_exported_at = timezone.now()
            shop.save(update_fields=['last_transaction_exported_at'])
            
            # Create export history record
            export_history = ExportHistory.objects.create(shop=shop, export_type='transactions')
            
            # Create ExportDetails for each exported record
            try:
                # Handle all export modes and create detail entries
                if export_mode == 'all':
                    # Create details for all types, accounts, and transactions
                    for type_data in export_data.get('types', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=type_data['id'],
                            record_type='Type',
                            status='success'
                        )
                    for account_data in export_data.get('accounts', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=account_data['id'],
                            record_type='Account',
                            status='success'
                        )
                    for trans_data in export_data.get('transactions', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=trans_data['id'],
                            record_type='Transaction',
                            status='success'
                        )
                elif export_mode == 'date_range':
                    # Create details for transactions in date range
                    for trans_data in export_data.get('transactions', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=trans_data['id'],
                            record_type='Transaction',
                            status='success'
                        )
                elif export_mode == 'after_last_export':
                    # Create details for all changed records
                    for type_data in export_data.get('types', {}).get('created', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=type_data['id'],
                            record_type='Type',
                            status='success',
                            message='Created'
                        )
                    for type_data in export_data.get('types', {}).get('updated', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=type_data['id'],
                            record_type='Type',
                            status='success',
                            message='Updated'
                        )
                    for type_data in export_data.get('types', {}).get('deleted', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=type_data['id'],
                            record_type='Type',
                            status='success',
                            message='Deleted'
                        )
                    for account_data in export_data.get('accounts', {}).get('created', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=account_data['id'],
                            record_type='Account',
                            status='success',
                            message='Created'
                        )
                    for account_data in export_data.get('accounts', {}).get('updated', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=account_data['id'],
                            record_type='Account',
                            status='success',
                            message='Updated'
                        )
                    for account_data in export_data.get('accounts', {}).get('deleted', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=account_data['id'],
                            record_type='Account',
                            status='success',
                            message='Deleted'
                        )
                    for trans_data in export_data.get('transactions', {}).get('created', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=trans_data['id'],
                            record_type='Transaction',
                            status='success',
                            message='Created'
                        )
                    for trans_data in export_data.get('transactions', {}).get('updated', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=trans_data['id'],
                            record_type='Transaction',
                            status='success',
                            message='Updated'
                        )
                    for trans_data in export_data.get('transactions', {}).get('deleted', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=trans_data['id'],
                            record_type='Transaction',
                            status='success',
                            message='Deleted'
                        )
            except Exception as e:
                logger.error(f"Error creating export details for export history {export_history.id}: {str(e)}", exc_info=True)
            
            # Return JSON with download headers
            from django.http import HttpResponse
            response = HttpResponse(
                json.dumps(export_data, indent=2, default=str),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="transactions_{shop.short_name}_{export_mode}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response
            
        except Exception as e:
            logger.error(f"Error exporting transactions for shop {pk}: {str(e)}", exc_info=True)
            return JsonResponse({'error': f'Error exporting transactions: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@admin_required
def edit_shop(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    if request.method == 'POST':
        form = ShopEditForm(request.POST, instance=shop)
        if form.is_valid():
            try:
                form.save()
                logger.info(f"Shop edited by {request.user.username}: {pk}")
                messages.success(request, f'Shop "{shop.name}" updated successfully!')
                return redirect('manager:shop_info', pk=shop.pk)
            except Exception as e:
                logger.error(f"Error editing shop {pk} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while updating shop.')
    else:
        form = ShopEditForm(instance=shop)
    return render(request, 'manager/edit_shop.html', {'nav_title': 'Shops', 'form': form, 'shop': shop, 'app_name': 'manager','is_super_admin': request.user.is_superuser,})


@login_required
@super_admin_required
def delete_shop(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    if request.method == 'POST':
        has_ledgers = Ledger.objects.filter(shop=shop).exists()
        has_transactions = Transactions.objects.filter(shop=shop).exists()
        has_loans = Loan.objects.filter(shop=shop).exists()
        if has_ledgers or has_transactions or has_loans:
            messages.error(request, f'Cannot delete shop "{shop.name}" because it has linked ledgers, transactions, or loans.')
            logger.warning(f"Shop deletion blocked by {request.user.username}: {shop.name} has associations")
            return redirect('manager:shop_info', pk=shop.pk)
        shop_name = shop.name
        try:
            shop.delete()
            logger.warning(f"Shop deleted by {request.user.username}: {shop_name}")
            messages.success(request, f'Shop "{shop_name}" deleted successfully!')
        except Exception as e:
            logger.error(f"Error deleting shop {shop_name} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting shop.')
            return redirect('manager:shop_info', pk=pk)
        return redirect('manager:home')
    return render(request, 'manager/delete_shop.html', {'nav_title': 'Shops', 'shop': shop, 'app_name': 'manager','is_super_admin': request.user.is_superuser,})


@login_required
@admin_required
def add_shop_ledger(request, shop_pk):
    shop = get_object_or_404(Shop, pk=shop_pk)
    if request.method == 'POST':
        form = LedgerForm(request.POST)
        if form.is_valid():
            try:
                with db_transaction.atomic():
                    ledger = form.save(commit=False)
                    ledger.shop = shop
                    ledger.save()

                messages.success(request, f'Ledger "{ledger.name}" created for shop "{shop.name}"!')
                return redirect('manager:shop_info', pk=shop.pk)
            except Exception as e:
                logger.error(f"Error creating ledger for shop {shop.name} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while creating ledger.')
    else:
        form = LedgerForm()

    return render(request, 'manager/add_shop_ledger.html', {
        'nav_title':'Shops',
        'form': form,
        'shop': shop,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
    })

@login_required
@admin_required
def ledger_info(request, pk):
    ledger = get_object_or_404(Ledger, pk=pk)
    
    # Get all loan transactions for this ledger
    loans_list = Loan.objects.filter(ledger=ledger).order_by('-transaction_dt')
    
    # Pagination
    paginator = Paginator(loans_list, 25)  # Show 25 loans per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate counts for loans and releases
    loan_count = Loan.objects.filter(ledger=ledger, type='LOAN').count()
    release_count = Loan.objects.filter(ledger=ledger, type='RELEASE').count()
    
    context = {
        'nav_title': 'Shops',
        'ledger': ledger,
        'page_obj': page_obj,
        'loan_count': loan_count,
        'release_count': release_count,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'app_name': 'manager',
    }
    return render(request, 'manager/ledger_info.html', context)


@login_required
@admin_required
def edit_ledger(request, pk):
    ledger = get_object_or_404(Ledger, pk=pk)
    old_name = ledger.name
    
    if request.method == 'POST':
        form = LedgerForm(request.POST, instance=ledger)
        if form.is_valid():
            try:
                updated_ledger = form.save()
                changes = []
                if old_name != updated_ledger.name:
                    changes.append(f"name: {old_name} -> {updated_ledger.name}")
                change_summary = ', '.join(changes) if changes else 'no changes'
                logger.info(f"Ledger edited by {request.user.username}: ID {pk}, changes: {change_summary}")
                messages.success(request, f'Ledger "{ledger.name}" updated successfully!')
                return redirect('manager:ledger_info', pk=ledger.pk)
            except Exception as e:
                logger.error(f"Error editing ledger {pk} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while updating ledger.')
    else:
        form = LedgerForm(instance=ledger)
    
    context = {
        'nav_title': 'Shops',
        'form': form,
        'ledger': ledger,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'manager/edit_ledger.html', context)


@login_required
@admin_required
def delete_ledger(request, pk):
    ledger = get_object_or_404(Ledger, pk=pk)
    
    if request.method == 'POST':
        # Check if ledger has transactions (via shop)
        if Transactions.objects.filter(shop=ledger.shop).exists():
            messages.error(request, f'Cannot delete ledger "{ledger.name}" because its shop has associated transactions.')
            logger.warning(f"Ledger deletion blocked by {request.user.username}: {ledger.name} shop has associated transactions")
            return redirect('manager:ledger_info', pk=ledger.pk)
        
        ledger_name = ledger.name
        try:
            ledger.delete()
            logger.warning(f"Ledger deleted by {request.user.username}: {ledger_name}")
            messages.success(request, f'Ledger "{ledger_name}" deleted successfully!')
        except Exception as e:
            logger.error(f"Error deleting ledger {ledger_name} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting ledger.')
            return redirect('manager:ledger_info', pk=ledger.pk)
        return redirect('manager:home')
    
    context = {
        'nav_title': 'Shops',
        'ledger': ledger,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'manager/delete_ledger.html', context)

@login_required
@admin_required
def configurations(request):
    """List and edit all configurations in one page"""
    if request.method == 'POST':
        # Get all submitted config values
        for key, value in request.POST.items():
            if key.startswith('config_'):
                config_key = key.replace('config_', '', 1)
                try:
                    config = Configuration.objects.get(key=config_key)
                    config.value = value
                    config.save()
                except Configuration.DoesNotExist:
                    pass
        messages.success(request, 'Configurations updated successfully!')
        return redirect('manager:configurations')

    # Group configs for display
    configs = Configuration.objects.all().order_by('group', 'key')
    grouped = {}
    for config in configs:
        if config.group not in grouped:
            grouped[config.group] = []
        grouped[config.group].append(config)

    return render(request, 'manager/configurations.html', {
        'nav_title': 'Configurations',
        'grouped_configs': grouped.items(),
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })

@login_required
@admin_required
def import_transactions(request):
    """Import transactions, types, and accounts from JSON file exported from sync"""
    if request.method == 'POST' and request.FILES.get('json_file'):
        try:
            json_file = request.FILES['json_file']
            import_data = json.load(json_file)
            
            # Get or create system user for import tracking
            system_user = User.objects.filter(username='system').first()
            if not system_user:
                system_user = User.objects.create_user(
                    username='system',
                    first_name='System',
                    last_name='Automated',
                    is_active=False,
                )
                logger.info("Created system user for import tracking")
            
            shop_id = import_data.get('shop_id')
            shop = get_object_or_404(Shop, pk=shop_id) if shop_id else None
            
            if not shop:
                return JsonResponse({'error': 'Shop ID not found in import file'}, status=400)
            
            with db_transaction.atomic():
                import_history = ImportHistory.objects.create(
                    shop=shop,
                    import_type='transactions'
                )
                
                types_created = 0
                types_updated = 0
                accounts_created = 0
                accounts_updated = 0
                transactions_created = 0
                transactions_updated = 0
                
                # Handle both formats: flat (direct arrays) and nested (created/updated/deleted)
                types_data = []
                accounts_data = []
                transactions_data = []
                
                # Check if it's nested format (with created/updated/deleted)
                if 'types' in import_data and isinstance(import_data['types'], dict):
                    # Nested format from incremental export
                    types_data = (import_data['types'].get('created', []) + 
                                 import_data['types'].get('updated', []) + 
                                 import_data['types'].get('deleted', []))
                    accounts_data = (import_data['accounts'].get('created', []) + 
                                    import_data['accounts'].get('updated', []) + 
                                    import_data['accounts'].get('deleted', []))
                    transactions_data = (import_data['transactions'].get('created', []) + 
                                        import_data['transactions'].get('updated', []) + 
                                        import_data['transactions'].get('deleted', []))
                else:
                    # Flat format from full export
                    types_data = import_data.get('types', [])
                    accounts_data = import_data.get('accounts', [])
                    transactions_data = import_data.get('transactions', [])
                
                # Import Types
                for type_data in types_data:
                    try:
                        type_id = type_data.get('id', '').strip()
                        group_id = type_data.get('group_id')
                        
                        try:
                            group = Group.objects.get(id=group_id) if group_id else None
                        except Group.DoesNotExist:
                            group = None
                        
                        if type_id and Type.objects.filter(id=type_id).exists():
                            # Update existing
                            Type.objects.filter(id=type_id).update(
                                e_name=type_data.get('e_name', ''),
                                t_name=type_data.get('t_name', ''),
                                shop=shop,
                                group=group
                            )
                            types_updated += 1
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=type_id,
                                record_type='Type',
                                status='success',
                                message='Updated'
                            )
                        else:
                            # Create new
                            Type.objects.create(
                                id=type_id if type_id else None,
                                e_name=type_data.get('e_name', ''),
                                t_name=type_data.get('t_name', ''),
                                shop=shop,
                                group=group
                            )
                            types_created += 1
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=type_id if type_id else 'auto',
                                record_type='Type',
                                status='success',
                                message='Created'
                            )
                    except Exception as e:
                        logger.error(f"Error importing type {type_data.get('id')}: {str(e)}")
                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=type_data.get('id', 'unknown'),
                            record_type='Type',
                            status='failed',
                            message=f'Error: {str(e)}'
                        )
                
                # Import Accounts
                for account_data in accounts_data:
                    try:
                        account_id = account_data.get('id', '').strip()
                        acc_type_id = account_data.get('acc_type_id')
                        
                        try:
                            acc_type = Type.objects.get(id=acc_type_id, shop=shop) if acc_type_id else None
                        except Type.DoesNotExist:
                            acc_type = None
                        
                        if account_id and Accounts.objects.filter(id=account_id).exists():
                            # Update existing
                            Accounts.objects.filter(id=account_id).update(
                                e_name=account_data.get('e_name', ''),
                                t_name=account_data.get('t_name', ''),
                                shop=shop,
                                acc_type=acc_type,
                                priority=account_data.get('priority', 0),
                                is_admin_only=account_data.get('is_admin_only', False)
                            )
                            accounts_updated += 1
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=account_id,
                                record_type='Account',
                                status='success',
                                message='Updated'
                            )
                        else:
                            # Create new
                            Accounts.objects.create(
                                id=account_id if account_id else None,
                                e_name=account_data.get('e_name', ''),
                                t_name=account_data.get('t_name', ''),
                                shop=shop,
                                acc_type=acc_type,
                                priority=account_data.get('priority', 0),
                                is_admin_only=account_data.get('is_admin_only', False)
                            )
                            accounts_created += 1
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=account_id if account_id else 'auto',
                                record_type='Account',
                                status='success',
                                message='Created'
                            )
                    except Exception as e:
                        logger.error(f"Error importing account {account_data.get('id')}: {str(e)}")
                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=account_data.get('id', 'unknown'),
                            record_type='Account',
                            status='failed',
                            message=f'Error: {str(e)}'
                        )
                
                # Import Transactions
                for trans_data in transactions_data:
                    try:
                        trans_id = trans_data.get('id', '').strip()
                        account_id = trans_data.get('account_id')
                        
                        try:
                            account = Accounts.objects.get(id=account_id, shop=shop) if account_id else None
                        except Accounts.DoesNotExist:
                            account = None
                        
                        if not account:
                            raise ValueError(f"Account {account_id} not found")
                        
                        # Parse datetime
                        trans_dt = trans_data.get('transaction_dt')
                        if isinstance(trans_dt, str):
                            trans_dt = datetime.fromisoformat(trans_dt.replace('Z', '+00:00'))
                        
                        # Convert amount to Decimal
                        amount = Decimal(str(trans_data.get('amount', 0)))
                        
                        if trans_id and Transactions.objects.filter(id=trans_id).exists():
                            # Update existing
                            Transactions.objects.filter(id=trans_id).update(
                                acc=account,
                                transaction_dt=trans_dt,
                                amount=amount,
                                tr_type=trans_data.get('tr_type', 'DEBIT'),
                                remarks=trans_data.get('remarks', ''),
                                name=trans_data.get('name', ''),
                                is_tally=trans_data.get('is_tally', False),
                                shop=shop,
                                updated_by=system_user,
                                updated_at=timezone.now()
                            )
                            transactions_updated += 1
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=trans_id,
                                record_type='Transaction',
                                status='success',
                                message='Updated'
                            )
                        else:
                            # Create new
                            Transactions.objects.create(
                                id=trans_id if trans_id else None,
                                acc=account,
                                transaction_dt=trans_dt,
                                amount=amount,
                                tr_type=trans_data.get('tr_type', 'DEBIT'),
                                remarks=trans_data.get('remarks', ''),
                                name=trans_data.get('name', ''),
                                is_tally=trans_data.get('is_tally', False),
                                shop=shop,
                                created_by=system_user,
                                updated_by=system_user
                            )
                            transactions_created += 1
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=trans_id if trans_id else 'auto',
                                record_type='Transaction',
                                status='success',
                                message='Created'
                            )
                    except Exception as e:
                        logger.error(f"Error importing transaction {trans_data.get('id')}: {str(e)}")
                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=trans_data.get('id', 'unknown'),
                            record_type='Transaction',
                            status='failed',
                            message=f'Error: {str(e)}'
                        )
                
                # Update shop's last import timestamp
                shop.last_transaction_imported_at = timezone.now()
                shop.save(update_fields=['last_transaction_imported_at'])
                
                logger.info(
                    f"Import completed for shop {shop.id}: "
                    f"Types(C:{types_created}/U:{types_updated}), "
                    f"Accounts(C:{accounts_created}/U:{accounts_updated}), "
                    f"Transactions(C:{transactions_created}/U:{transactions_updated})"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Import completed successfully',
                    'summary': {
                        'types': {'created': types_created, 'updated': types_updated},
                        'accounts': {'created': accounts_created, 'updated': accounts_updated},
                        'transactions': {'created': transactions_created, 'updated': transactions_updated},
                    }
                })
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON file: {str(e)}")
            return JsonResponse({'error': f'Invalid JSON file: {str(e)}'}, status=400)
        except Exception as e:
            logger.error(f"Error during import: {str(e)}", exc_info=True)
            return JsonResponse({'error': f'Import error: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'No file provided'}, status=400)


@login_required
@admin_required
def activity_logs(request):
    selected_user = request.GET.get('selected_user')

    logs = ActivityLog.objects.select_related('user').order_by('-created_at')
    users = User.objects.all()
    
    if selected_user:
        logs = logs.filter(user__id=selected_user)

    return render(request, 'manager/activity_logs.html', {
        'nav_title': 'Activity Logs',
        'selected_user': int(selected_user) if selected_user else "",
        'logs': logs,
        'users': users,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })

def sync_grp_typ(request,pk):
    shop = Shop.objects.get(pk=pk)
    manager_helper.sync_groups_and_types(request,shop)
    return redirect('manager:shop_info', pk=shop.id)

def add_account(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    if request.method == 'POST':
        form = AccountsForm(request.POST, shop=shop) # Pass shop here
        if form.is_valid():
            chosen_date = form.cleaned_data.get('date')
            chosen_time = form.cleaned_data.get('time') or timezone.localtime(timezone.now()).time()
            account = form.save(commit=False)
            transaction_dt_value = timezone.make_aware(
                datetime.combine(chosen_date, chosen_time)
            )
            account.shop = shop
            account.priority = 1
            account.save()
            manager_helper.log_activity(request, 'CREATE', 'Accounts', account.id, f'Created account {account.t_name} in shop {shop.name}', shop)

            if form.cleaned_data['balance'] is not None and form.cleaned_data['balance'] > 0.00:
                transaction = Transactions.objects.create(
                    amount=form.cleaned_data['balance'] or 0.00,  # dict access, not a call
                    name='',
                    shop=shop,
                    tr_type='CREDIT',
                    remarks='Opening Balance',  # also fixed the typo
                    acc=account,                # ✅ correct field name (was 'account')
                    transaction_dt=transaction_dt_value,  # ✅ use the pre-computed value
                    created_by=request.user if request.user.is_authenticated else None,
                    updated_by=request.user if request.user.is_authenticated else None,
                )
                manager_helper.log_activity(request, 'CREATE', 'Transaction', transaction.id, f'Created opening balance transaction for account {account.t_name} with amount {form.cleaned_data["balance"]}', shop)
            return redirect('manager:shop_info',pk=shop.id)
    else:
        form = AccountsForm(shop=shop) # Pass shop here
    return render(request, 'manager/add_account.html', {
        'form': form,
        'shop': shop,
        'nav_title': 'Shops',
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),})

def account_info(request, pk):
    account = get_object_or_404(Accounts, pk=pk)
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()
    
    start_date, end_date = date_helper.get_fy_dates(fy)
    transactions = Transactions.objects.filter(
        acc=account,
        transaction_dt__date__gte=start_date,
        transaction_dt__date__lte=end_date,
    ).order_by('-transaction_dt')
    balance = transaction_helper.get_account_balance(account)  # Calculate balance for this account
    shop_accounts = Accounts.objects.filter(shop=account.shop).exclude(pk=account.pk).order_by('t_name')
    return render(request, 'manager/account_info.html', {
        'nav_title': 'Shops',
        'account': account,
        'balance': balance,
        'transactions': transactions,
        'shop_accounts': shop_accounts,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })

def account_edit(request, pk):
    account = get_object_or_404(Accounts, pk=pk)
    if request.method == 'POST':
        form = AccountsEditForm(request.POST, instance=account, shop=account.shop) # Pass shop here
        if form.is_valid():
            form.save()
            manager_helper.log_activity(request, 'UPDATE', 'Accounts', account.id, f'Edited account {account.t_name} in shop {account.shop.name}', account.shop)
            return redirect('manager:account_info', pk=account.id)
    else:
        form = AccountsEditForm(instance=account, shop=account.shop) # Pass shop here
    return render(request, 'manager/edit_account.html', {
        'form': form,
        'account': account,
        'nav_title': 'Shops',
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })

@login_required
@admin_required
def delete_account(request, pk):
    """Delete an account"""
    account = get_object_or_404(Accounts, pk=pk)
    
    if request.method == 'POST':
        # Check if account has transactions
        if Transactions.objects.filter(acc=account).exists():
            messages.error(request, f'Cannot delete account "{account.t_name}" because it has associated transactions.')
            logger.warning(f"Account deletion blocked by {request.user.username}: {account.t_name} has associated transactions")
            return redirect('manager:account_info', pk=account.pk)
        
        account_name = account.e_name
        shop_id = account.shop.id
        try:
            manager_helper.log_activity(request, 'DELETE', 'Accounts', account.id, f'Deleted account {account.t_name} from shop {account.shop.name}', account.shop)
            account.delete()
            logger.warning(f"Account deleted by {request.user.username}: {account_name}")
            messages.success(request, f'Account "{account_name}" deleted successfully!')
        except Exception as e:
            logger.error(f"Error deleting account {account_name} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting account.')
            return redirect('manager:account_info', pk=pk)
        return redirect('manager:shop_info', pk=shop_id)
    
    context = {
        'nav_title': 'Shops',
        'account': account,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'manager/delete_account.html', context)

@login_required
@admin_required
def move_transactions(request):
    """Move transactions from one account to another"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        transaction_ids = data.get('transaction_ids', [])
        target_account_id = data.get('target_account_id')
        
        if not transaction_ids or not target_account_id:
            return JsonResponse({'success': False, 'message': 'Missing required parameters'}, status=400)
        
        target_account = get_object_or_404(Accounts, pk=target_account_id)
        
        # Update transactions in a transaction block
        with db_transaction.atomic():
            for transaction_id in transaction_ids:
                manager_helper.log_activity(request, 'UPDATE', 'Transaction', transaction_id, f'Moved transaction ID {transaction_id} to account {target_account.t_name}', target_account.shop)
            Transactions.objects.filter(id__in=transaction_ids).update(acc=target_account)
            manager_helper.update_account_priority(target_account, increment=len(transaction_ids))
        logger.info(f"Moved {len(transaction_ids)} transactions to account {target_account.id} by user {request.user.username}")
        
        return JsonResponse({'success': True, 'message': f'Successfully moved {len(transaction_ids)} transaction(s)'})
    
    except Exception as e:
        logger.error(f"Error moving transactions: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@admin_required
def update_tally_transactions(request):
    """Update tally status for transactions"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        transaction_ids = data.get('transaction_ids', [])
        is_tally = data.get('is_tally', False)
        
        if not transaction_ids:
            return JsonResponse({'success': False, 'message': 'Missing transaction IDs'}, status=400)
        
        # Update transactions in a transaction block
        with db_transaction.atomic():
            for transaction_id in transaction_ids:
                transaction = Transactions.objects.get(id=transaction_id)
                manager_helper.log_activity(request, 'UPDATE', 'Transaction', transaction_id, f'Updated tally status to {is_tally} for transaction ID {transaction_id}', transaction.shop)
            Transactions.objects.filter(id__in=transaction_ids).update(is_tally=is_tally)
        
        tally_status = 'Tallied' if is_tally else 'Not Tallied'
        logger.info(f"Updated {len(transaction_ids)} transactions to '{tally_status}' by user {request.user.username}")
        
        return JsonResponse({'success': True, 'message': f'Successfully updated {len(transaction_ids)} transaction(s) to {tally_status}'})
    
    except Exception as e:
        logger.error(f"Error updating tally transactions: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@admin_required
def balance_sheet(request):
    """Display group balance sheet summary for selected financial year"""
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()
    
    # Fetch all groups ordered by their order field
    groups = Group.objects.all().order_by('order')
    
    group_summaries = []
    
    for group in groups:
        summary = transaction_helper.get_group_summary(group, fy)
        # Calculate net balance (closing - opening = credits - debits)
        net_balance = summary['closing'] - summary['opening']
        
        group_summaries.append({
            'id': group.id,
            'order': group.order,
            'name': group.t_name,
            'opening': summary['opening'],
            'closing': summary['closing'],
        })
    
    # print(group_summaries)
    net_worth_opening = group_summaries[3]['opening'] + group_summaries[4]['opening'] + group_summaries[5]['opening']
    net_worth_closing = group_summaries[2]['closing'] + group_summaries[3]['closing'] + group_summaries[4]['closing']
    cash_in_hand_opening = group_summaries[0]['opening'] + group_summaries[1]['opening'] + group_summaries[2]['opening'] + group_summaries[3]['opening'] + group_summaries[4]['opening'] + group_summaries[5]['opening']
    cash_in_hand_closing = group_summaries[0]['closing'] + group_summaries[1]['closing'] + group_summaries[2]['closing'] + group_summaries[3]['closing'] + group_summaries[4]['closing'] + group_summaries[5]['closing']

    
    return render(request, 'manager/balance_sheet.html', {
        'nav_title': 'Balance Sheet',
        'fy': fy,
        'group_summaries': group_summaries,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'net_worth_opening': net_worth_opening,
        'net_worth_closing': net_worth_closing,
        'cash_in_hand_opening': cash_in_hand_opening,
        'cash_in_hand_closing': cash_in_hand_closing,
    })

def type_balance_sheet(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()

    # ✅ Fetch all groups ordered by their order field
    groups = Group.objects.all().order_by('order')

    grouped_list = []

    for group in groups:
        # ✅ Only types belonging to this shop AND this group
        types = Type.objects.filter(shop=shop, group=group).order_by('e_name')

        if not types.exists():
            continue  # ✅ Skip groups with no types for this shop

        type_entries = []

        for acc_type in types:
            summary = transaction_helper.get_type_summary(acc_type, fy)
            type_entries.append({
                'id':          acc_type.id,
                'name':        acc_type.t_name,
                'opening':     summary['opening'],
                'credits':     summary['credits'],
                'debits':      summary['debits'],
                'closing':     summary['closing'],
                'net_balance': summary['net_balance'],
                'cur_balance': summary['cur_balance'],
            })

        grouped_list.append({
            'group_id':          group.id,
            'group_name':        group.t_name,
            'group_order':       group.order,
            'types':             type_entries,
        })

    return render(request, 'manager/summary_types.html', {
        'nav_title':      'Shops',
        'fy':             fy,
        'shop':           shop,
        'grouped_list':   grouped_list,  # ✅ replaces 'items'
        'app_name':       'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin':       is_admin(request.user),
    })

def account_balance_sheet(request, pk, type_pk):
    shop = Shop.objects.get(pk=pk)
    type_obj = get_object_or_404(Type, pk=type_pk, shop=shop)

    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()
    
    accounts = Accounts.objects.filter(acc_type=type_obj)
    account_balances = []

    for account in accounts:
        summary = transaction_helper.get_account_summary(account, fy)
        account_balances.append({
            'id':      account.id,
            'name':    account.t_name,
            'opening': summary['opening'],
            'credits': abs(summary['credits']),
            'debits':  abs(summary['debits']),
            'closing': summary['closing'],
            'net_balance': summary['net_balance'],
            'cur_balance': summary['cur_balance'],
        })
    # print(type_balances)

    return render(request, 'manager/summary_account.html', {
        'nav_title': 'Shops',
        'fy': fy,
        'shop': shop,
        'items': account_balances,
        'item_type': 'Account',
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })