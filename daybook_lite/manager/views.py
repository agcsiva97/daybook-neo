from datetime import datetime, timedelta
import json
import logging
from pyexpat.errors import messages
from decimal import Decimal, ROUND_HALF_UP
import urllib.parse
from django.urls import reverse


from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db import IntegrityError
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q, Sum 
from django.http import HttpResponse, JsonResponse
from django.conf import settings

from .helper import manager_helper, date_helper, report_helper
from .forms import LedgerForm, ShopForm, ShopEditForm, AccountsForm, AccountsEditForm
from django.core.paginator import Paginator
from django.contrib.auth import  get_user_model

from entries.views import admin_required, super_admin_required, is_admin
from .models import Configuration, Shop, ActivityLog, Ledger, Accounts, Type, ExportHistory, ImportHistory, ExportDetails, ImportDetails, BT_Ledger_Accounts
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
            'icon': 'fa-upload',
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
            'icon': 'fa-download',
            'badge_class': 'bg-info',
        })
    
    # Sort by timestamp (most recent first)
    sync_events.sort(key=lambda x: x['timestamp'], reverse=True)

    page_number = request.GET.get('page', 1)
    paginator = Paginator(sync_events, 10)
    page_obj = paginator.get_page(page_number)

    shops = Shop.objects.all().order_by('short_name')
    
    return render(request, 'manager/sync_history.html', {
        'nav_title': 'Sync History',
        'sync_events': page_obj.object_list,
        'page_obj': page_obj,
        'shops': shops,
        'total_events': paginator.count,
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

@login_required
@admin_required
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
                    group_order = type_data.get('group_order') or type_data.get('group_id', 0)
                    
                    if not type_id:
                        type_obj = Type.objects.create(
                            e_name=type_data.get('e_name', ''),
                            t_name=type_data.get('t_name', ''),
                            shop=shop,
                            group_order=group_order
                        )
                    else:
                        type_obj, created = Type.objects.update_or_create(
                            id=type_id,
                            defaults={
                                'e_name': type_data.get('e_name', ''),
                                't_name': type_data.get('t_name', ''),
                                'shop': shop,
                                'group_order': group_order
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
                
                # Import Linked Accounts (BT_Ledger_Accounts)
                linked_accounts_created = 0
                linked_accounts_updated = 0
                for linked_acc_data in import_data.get('linked_accounts', []):
                    try:
                        ledger_id = linked_acc_data.get('ledger_id')
                        account_id = linked_acc_data.get('account_id')
                        rel_type = linked_acc_data.get('rel_type')

                        if not rel_type:
                            logger.warning(f"Skipping linked account import: missing rel_type for ledger {ledger_id}")
                            continue

                        try:
                            ledger = Ledger.objects.get(id=ledger_id)
                            account = Accounts.objects.get(id=account_id)
                        except (Ledger.DoesNotExist, Accounts.DoesNotExist):
                            logger.warning(f"Skipping linked account import: ledger {ledger_id} or account {account_id} not found")
                            continue

                        with db_transaction.atomic():
                            linked_acc, created = BT_Ledger_Accounts.objects.update_or_create(
                                ledger=ledger,
                                rel_type=rel_type,
                                defaults={
                                    'account': account,
                                    'shop': shop,
                                    'updated_by': request.user,
                                }
                            )
                            if created:
                                linked_acc.created_by = request.user
                                linked_acc.save(update_fields=['created_by'])
                                linked_accounts_created += 1
                            else:
                                linked_accounts_updated += 1
                    except Exception as e:
                        logger.warning(f"Error importing linked account: {str(e)}")
                        continue

                linked_account_count = linked_accounts_created + linked_accounts_updated
                
                # Update last import timestamp
                shop.last_transaction_imported_at = timezone.now()
                shop.save(update_fields=['last_transaction_imported_at'])
                
                # Create import history record
                ImportHistory.objects.create(shop=shop, import_type='shop')
                
                messages.success(request, f'Shop imported successfully! Shop: {shop.short_name}, Ledgers: {ledger_count}, Types: {type_count}, Accounts: {account_count}, Linked Accounts: {linked_account_count}')
                logger.info(f"Shop import completed: {shop.id} - Ledgers: {ledger_count}, Types: {type_count}, Accounts: {account_count}, Linked Accounts: {linked_account_count}")
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
                        manager_helper.sync_types(request, shop)
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
        account.group_name = manager_helper.get_group(account.acc_type.group_order)[2]
        account.group_order = account.acc_type.group_order

    accounts_list = sorted(accounts_list, key=lambda x: (x.group_order, x.priority, x.t_name))  # Sort by group order, then priority, then name
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
                'group_order': type_obj.group_order,
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
        
        # Get related ledger accounts (linked accounts)
        linked_accounts_data = []
        for ledger_account in BT_Ledger_Accounts.objects.filter(shop=shop).select_related('ledger', 'account'):
            linked_accounts_data.append({
                'id': ledger_account.id,
                'ledger_id': ledger_account.ledger_id,
                'shop_id': ledger_account.shop_id,
                'rel_type': ledger_account.rel_type,
                'account_id': ledger_account.account_id,
            })
        
        # Build export data
        export_data = {
            'shop': shop_data,
            'ledgers': ledgers_data,
            'types': types_data,
            'accounts': accounts_data,
            'linked_accounts': linked_accounts_data,
            'export_date': timezone.now().isoformat(),
        }
        
        # Return JSON with download headers
        from django.http import HttpResponse
        
        # Create export history record
        # ExportHistory.objects.create(shop=shop, export_type='shop')
        
        response = HttpResponse(
            json.dumps(export_data, indent=2, default=str,ensure_ascii=False),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="shop_{shop.short_name}_export.json"'
        return response
        
    except Exception as e:
        logger.error(f"Error exporting shop {pk}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Error exporting shop: {str(e)}'}, status=500)

# ── Helper to serialize a loan ───────────────────────────────
def _serialize_loan(loan_obj):
    return {
        'id': loan_obj.id,
        'pawn_no': loan_obj.pawn_no,
        'shop_id': loan_obj.shop_id,
        'ledger_id': loan_obj.ledger_id,
        'type': loan_obj.type,
        'principal': str(loan_obj.principal),
        'interest': str(loan_obj.interest),
        'transaction_dt': loan_obj.transaction_dt.isoformat(),
        'created_at': loan_obj.created_at.isoformat(),
        'updated_at': loan_obj.updated_at.isoformat() if loan_obj.updated_at else '',
        'created_by': loan_obj.created_by.username if loan_obj.created_by else '',
        'updated_by': loan_obj.updated_by.username if loan_obj.updated_by else '',
    }

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
                        'group_order': type_obj.group_order,
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
                        'loan_tr_type': trans.loan_tr_type,
                        'remarks': trans.remarks or '',
                        'is_tally': trans.is_tally,
                        'created_at': trans.created_at.isoformat(),
                        'updated_at': trans.updated_at.isoformat() if trans.updated_at else '',
                        'created_by': trans.created_by.username if trans.created_by else '',
                        'updated_by': trans.updated_by.username if trans.updated_by else '',
                    })
                
                # Get all linked accounts associated with shop
                linked_accounts_qs = BT_Ledger_Accounts.objects.filter(shop=shop).select_related('ledger', 'account')
                linked_accounts_data = []
                for linked_acc in linked_accounts_qs:
                    linked_accounts_data.append({
                        'id': linked_acc.id,
                        'ledger_id': linked_acc.ledger_id,
                        'shop_id': linked_acc.shop_id,
                        'rel_type': linked_acc.rel_type,
                        'account_id': linked_acc.account_id,
                    })
                
                # Loans — all
                loans_qs   = Loan.objects.filter(shop=shop).order_by('transaction_dt')
                loans_data = [_serialize_loan(l) for l in loans_qs]
                
                export_data.update({
                    'types_count': len(types_data),
                    'types': types_data,
                    'accounts_count': len(accounts_data),
                    'accounts': accounts_data,
                    'transactions_count': len(transactions_data),
                    'transactions': transactions_data,
                    'linked_accounts_count': len(linked_accounts_data),
                    'linked_accounts': linked_accounts_data,
                })

                export_data.update({
                    'loans_count': len(loans_data),
                    'loans': loans_data,
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
                        'is_tally': trans.is_tally,
                        'created_at': trans.created_at.isoformat(),
                        'updated_at': trans.updated_at.isoformat() if trans.updated_at else '',
                        'created_by': trans.created_by.username if trans.created_by else '',
                        'updated_by': trans.updated_by.username if trans.updated_by else '',
                        'loan_tr_type': trans.loan_tr_type,
                    })
                
                # Get all linked accounts for this shop (always export current state)
                linked_accounts_qs = BT_Ledger_Accounts.objects.filter(shop=shop).select_related('ledger', 'account')
                linked_accounts_data = []
                for linked_acc in linked_accounts_qs:
                    linked_accounts_data.append({
                        'id': linked_acc.id,
                        'ledger_id': linked_acc.ledger_id,
                        'shop_id': linked_acc.shop_id,
                        'rel_type': linked_acc.rel_type,
                        'account_id': linked_acc.account_id,
                    })
                
                # Loans — date range
                loans_qs   = Loan.objects.filter(shop=shop, transaction_dt__date__range=[from_dt, to_dt]).order_by('transaction_dt')
                loans_data = [_serialize_loan(l) for l in loans_qs]

                export_data.update({
                    'date_from': from_date,
                    'date_to': to_date,
                    'transactions_count': len(transactions_data),
                    'transactions': transactions_data,
                    'linked_accounts_count': len(linked_accounts_data),
                    'linked_accounts': linked_accounts_data,
                })

                export_data.update({
                    'loans_count': len(loans_data),
                    'loans': loans_data,
                })
                
            elif export_mode == 'after_last_export':
                # Export changes since last export using activity log
                last_export_time = shop.last_transaction_exported_at
                
                # If no last export exists, fetch all activity logs for the shop
                if last_export_time is None:
                    activity_logs = ActivityLog.objects.filter(
                        shop=shop,
                        model_name__in=['Type', 'Accounts', 'Transaction', 'Loan'],
                        action__in=['CREATE', 'UPDATE', 'DELETE']
                    ).order_by('created_at')
                else:
                    # Get activity logs after last export for relevant models
                    # Use __gte (>=) instead of __gt (>) to include logs at the exact export timestamp
                    # and catch any records that might have been created at the boundary
                    activity_logs = ActivityLog.objects.filter(
                        shop=shop,
                        created_at__gte=last_export_time,
                        model_name__in=['Type', 'Accounts', 'Transaction', 'Loan'],
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
                loans_created = []
                loans_updated = []
                loans_deleted = []
                
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
                                        'group_order': type_obj.group_order,
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
                                        'group_id': type_obj.group_order,
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
                                        'loan_tr_type': trans.loan_tr_type,
                                        'remarks': trans.remarks or '',
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
                                        'loan_tr_type': trans.loan_tr_type,
                                        'remarks': trans.remarks or '',
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
                        elif log.model_name.lower() == 'loan':
                            if log.action == 'CREATE':
                                try:
                                    loan_obj = Loan.objects.get(id=log.object_id, shop=shop)
                                    loans_created.append(_serialize_loan(loan_obj))
                                except Loan.DoesNotExist:
                                    pass
                            elif log.action == 'UPDATE':
                                try:
                                    loan_obj = Loan.objects.get(id=log.object_id, shop=shop)
                                    loans_updated.append(_serialize_loan(loan_obj))
                                except Loan.DoesNotExist:
                                    pass
                            elif log.action == 'DELETE':
                                loans_deleted.append({
                                    'id': log.object_id,
                                    'description': log.description,
                                    'deleted_at': log.created_at.isoformat(),
                                })
                    except Exception as e:
                        logger.warning(f"Error processing activity log {log.id}: {str(e)}")
                        continue
                
                # Always export current state of all linked accounts for this shop
                linked_accounts_qs = BT_Ledger_Accounts.objects.filter(shop=shop).select_related('ledger', 'account')
                linked_accounts_data = []
                for linked_acc in linked_accounts_qs:
                    linked_accounts_data.append({
                        'id': linked_acc.id,
                        'ledger_id': linked_acc.ledger_id,
                        'shop_id': linked_acc.shop_id,
                        'rel_type': linked_acc.rel_type,
                        'account_id': linked_acc.account_id,
                    })
                
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
                    'linked_accounts_count': len(linked_accounts_data),
                    'linked_accounts': linked_accounts_data,
                    'loans': {
                        'created': loans_created,
                        'updated': loans_updated,
                        'deleted': loans_deleted,
                    },
                })
            
            elif export_mode == 'export_from':
                # Export changes since user-specified date using activity log
                export_from_date_str = request.POST.get('export_from_date')
                
                if not export_from_date_str:
                    return JsonResponse({'error': 'Export From Date is required for export_from mode'}, status=400)
                
                try:
                    export_from_date = datetime.strptime(export_from_date_str, '%Y-%m-%d').date()
                    export_from_dt = timezone.make_aware(datetime.combine(export_from_date, datetime.min.time()))
                except (ValueError, AttributeError) as e:
                    return JsonResponse({'error': f'Invalid date format for export_from_date. Expected YYYY-MM-DD: {str(e)}'}, status=400)
                
                # Get activity logs after the specified export_from date for relevant models
                activity_logs = ActivityLog.objects.filter(
                    shop=shop,
                    created_at__gte=export_from_dt,
                    model_name__in=['Type', 'Accounts', 'Transaction', 'Loan'],
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
                loans_created = []
                loans_updated = []
                loans_deleted = []
                
                for log in activity_logs:
                    try:
                        if log.model_name.lower() == 'type':
                            if log.action == 'CREATE':
                                try:
                                    type_obj = Type.objects.get(id=log.object_id, shop=shop)
                                    types_created.append({
                                        'id': type_obj.id,
                                        'e_name': type_obj.e_name or '',
                                        't_name': type_obj.t_name or '',
                                        'shop_id': type_obj.shop_id,
                                        'group_id': type_obj.group_order,
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
                                        'group_id': type_obj.group_order,
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
                                        'loan_tr_type': trans.loan_tr_type,
                                        'remarks': trans.remarks or '',
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
                                        'loan_tr_type': trans.loan_tr_type,
                                        'remarks': trans.remarks or '',
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
                        elif log.model_name.lower() == 'loan':
                            if log.action == 'CREATE':
                                try:
                                    loan_obj = Loan.objects.get(id=log.object_id, shop=shop)
                                    loans_created.append(_serialize_loan(loan_obj))
                                except Loan.DoesNotExist:
                                    pass
                            elif log.action == 'UPDATE':
                                try:
                                    loan_obj = Loan.objects.get(id=log.object_id, shop=shop)
                                    loans_updated.append(_serialize_loan(loan_obj))
                                except Loan.DoesNotExist:
                                    pass
                            elif log.action == 'DELETE':
                                loans_deleted.append({
                                    'id': log.object_id,
                                    'description': log.description,
                                    'deleted_at': log.created_at.isoformat(),
                                })
                    except Exception as e:
                        logger.warning(f"Error processing activity log {log.id}: {str(e)}")
                        continue
                
                # Always export current state of all linked accounts for this shop
                linked_accounts_qs = BT_Ledger_Accounts.objects.filter(shop=shop).select_related('ledger', 'account')
                linked_accounts_data = []
                for linked_acc in linked_accounts_qs:
                    linked_accounts_data.append({
                        'id': linked_acc.id,
                        'ledger_id': linked_acc.ledger_id,
                        'shop_id': linked_acc.shop_id,
                        'rel_type': linked_acc.rel_type,
                        'account_id': linked_acc.account_id,
                    })
                
                export_data.update({
                    'export_from_date': export_from_date_str,
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
                    'linked_accounts_count': len(linked_accounts_data),
                    'linked_accounts': linked_accounts_data,
                    'loans': {
                        'created': loans_created,
                        'updated': loans_updated,
                        'deleted': loans_deleted,
                    },
                })
            
            # Update last export timestamp (use the time captured at the start for consistency)
            if export_mode == 'after_last_export' or export_mode == 'export_from':
                shop.last_transaction_exported_at = current_export_time
            else:
                shop.last_transaction_exported_at = timezone.now()
            shop.save(update_fields=['last_transaction_exported_at'])

            exp_type = {
                'all': 'All Data Export',
                'after_last_export': 'Changes Since Last Export',
                'export_from': 'Changes Since Specified Date',
            }.get(export_mode, 'Transactions Export')
            
            # Create export history record
            export_history = ExportHistory.objects.create(shop=shop, export_type=exp_type)
            
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
                    for linked_acc_data in export_data.get('linked_accounts', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=linked_acc_data['id'],
                            record_type='BT_Ledger_Accounts',
                            status='success'
                        )
                    for loan_data in loans_data:
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=loan_data['id'],
                            record_type='Loan',
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
                    for linked_acc_data in export_data.get('linked_accounts', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=linked_acc_data['id'],
                            record_type='BT_Ledger_Accounts',
                            status='success'
                        )
                    for loan_data in loans_data:
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=loan_data['id'],
                            record_type='Loan',
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
                    for loan_data in export_data.get('loans', {}).get('created', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=loan_data['id'],
                            record_type='Loan',
                            status='success',
                            message='Created'
                        )
                    for loan_data in export_data.get('loans', {}).get('updated', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=loan_data['id'],
                            record_type='Loan',
                            status='success',
                            message='Updated'
                        )
                    for loan_data in export_data.get('loans', {}).get('deleted', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=loan_data['id'],
                            record_type='Loan',
                            status='success',
                            message='Deleted'
                        )
                    for linked_acc_data in export_data.get('linked_accounts', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=linked_acc_data['id'],
                            record_type='BT_Ledger_Accounts',
                            status='success'
                        )
                elif export_mode == 'export_from':
                    # Create details for all changed records (same pattern as after_last_export)
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
                    for loan_data in export_data.get('loans', {}).get('created', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=loan_data['id'],
                            record_type='Loan',
                            status='success',
                            message='Created'
                        )
                    for loan_data in export_data.get('loans', {}).get('updated', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=loan_data['id'],
                            record_type='Loan',
                            status='success',
                            message='Updated'
                        )
                    for loan_data in export_data.get('loans', {}).get('deleted', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=loan_data['id'],
                            record_type='Loan',
                            status='success',
                            message='Deleted'
                        )
                    for linked_acc_data in export_data.get('linked_accounts', []):
                        ExportDetails.objects.create(
                            export_history=export_history,
                            record_id=linked_acc_data['id'],
                            record_type='BT_Ledger_Accounts',
                            status='success'
                        )
            except Exception as e:
                logger.error(f"Error creating export details for export history {export_history.id}: {str(e)}", exc_info=True)
            
            # Return JSON with download headers
            from django.http import HttpResponse
            response = HttpResponse(
                json.dumps(export_data, indent=2, default=str, ensure_ascii=False),
                content_type='application/json'
            )
            now_utc = timezone.now()
            timestamp = timezone.localtime(now_utc).strftime("%Y_%m_%d_%H_%M_%S")
            response['Content-Disposition'] = f'attachment; filename="transactions_{shop.short_name}_{export_mode}_{timestamp}.json"'
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
@admin_required
def shop_meta(request, pk):
    shop = get_object_or_404(Shop, pk=pk)

    # Fetch all types for this shop, ordered by group_order then name
    types_qs = (
        Type.objects
        .filter(shop=shop)
        .prefetch_related('accounts')
        .order_by('group_order', 'e_name')
    )

    # Build hierarchy: group_order → [types with accounts + balances]
    groups_dict = {}
    for typ in types_qs:
        order = typ.group_order
        if order not in groups_dict:
            groups_dict[order] = {
                'order': order,
                'label': manager_helper.get_group(order)[2],
                'types': [],
                'type_count': 0,
                'account_count': 0,
            }

        # Annotate accounts with balance (fetch from your balance logic)
        accounts = list(typ.accounts.filter(shop=shop).order_by('priority', 'e_name'))

        # If you have a balance field/property on Accounts, use it directly.
        # Otherwise call your balance calculation utility here.
        for acc in accounts:
            acc.balance = transaction_helper.get_account_balance(acc)  # replace with your helper

        groups_dict[order]['types'].append({
            'obj': typ,
            'accounts': accounts,
        })
        groups_dict[order]['type_count'] += 1
        groups_dict[order]['account_count'] += len(accounts)

    hierarchy = sorted(groups_dict.values(), key=lambda g: g['order'])

    # Summary stats
    all_accounts = Accounts.objects.filter(shop=shop)
    total_accounts = all_accounts.count()
    total_types = types_qs.count()
    total_groups = len(hierarchy)

    # Shop-level balance (sum of all account balances)
    shop_balance = sum(
        transaction_helper.get_account_balance(acc) for acc in all_accounts
    )

    ledgers = Ledger.objects.filter(shop=shop).order_by('name')
    balance = transaction_helper.get_balance(shop)  # Calculate balance from transactions for accuracy

    return render(request, 'manager/shop_meta.html', {
        'shop': shop,
        'hierarchy': hierarchy,
        'total_groups': total_groups,
        'total_types': total_types,
        'total_accounts': total_accounts,
        'shop_balance': shop_balance,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'ledgers': ledgers,
        'balance': balance,
    })

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
    shop_accounts = Accounts.objects.filter(shop=ledger.shop).order_by('e_name')
    linked_accounts = BT_Ledger_Accounts.objects.filter(ledger=ledger).select_related('account')
    linked_accounts_dict = {acc.rel_type: acc.account for acc in linked_accounts}
    
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
        'shop_accounts': shop_accounts,
        'linked_accounts':linked_accounts,
        'linked_accounts_dict': linked_accounts_dict,
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

def _deleted_count(import_data, key):
    val = import_data.get(key, {})
    if isinstance(val, dict):
        return len(val.get('deleted', []))
    return 0

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
            
            # Ensure system_user was created/found successfully
            if not system_user:
                return JsonResponse({'error': 'Could not create or find system user for import tracking'}, status=500)
            
            logger.info(f"Import will use system user: {system_user.username} (ID: {system_user.id})")
            
            shop_id = import_data.get('shop_id')
            shop = get_object_or_404(Shop, pk=shop_id) if shop_id else None
            
            if not shop:
                return JsonResponse({'error': 'Shop ID not found in import file'}, status=400)
            imp_type = {
                'all': 'All Data Import',
                'after_last_export': 'Changes Since Last Import',
                'export_from': 'Changes Since Specified Date',
            }.get(import_data.get('export_mode', None), 'Transactions Import')

            with db_transaction.atomic():
                import_history = ImportHistory.objects.create(
                    shop=shop,
                    import_type=imp_type
                )
                
                types_created = 0
                types_updated = 0
                accounts_created = 0
                accounts_updated = 0
                transactions_created = 0
                transactions_updated = 0
                # ── Import Loans ─────────────────────────────────────────────
                loans_created = 0
                loans_updated = 0
                
                # Handle both formats: flat (direct arrays) and nested (created/updated/deleted)
                types_data = []
                accounts_data = []
                transactions_data = []
                loans_data = []
                
                # Check if it's nested format (with created/updated/deleted)
                if 'types' in import_data and isinstance(import_data['types'], dict):
                    # Nested format from incremental export
                    types_data        = import_data['types'].get('created', [])        + import_data['types'].get('updated', [])
                    accounts_data     = import_data['accounts'].get('created', [])     + import_data['accounts'].get('updated', [])
                    transactions_data = import_data['transactions'].get('created', []) + import_data['transactions'].get('updated', [])
                    loans_data        = import_data['loans'].get('created', [])        + import_data['loans'].get('updated', [])
                else:
                    # Flat format from full export
                    types_data = import_data.get('types', [])
                    accounts_data = import_data.get('accounts', [])
                    transactions_data = import_data.get('transactions', [])
                    loans_data = import_data.get('loans', [])
                
                # Import Types
                for type_data in types_data:
                    try:
                        type_id = type_data.get('id', '').strip()
                        group_order = type_data.get('group_order')
                        
                        if type_id and Type.objects.filter(id=type_id).exists():
                            # Update existing - use model instance to trigger history tracking
                            type_obj = Type.objects.get(id=type_id)
                            type_obj.e_name = type_data.get('e_name', '')
                            type_obj.t_name = type_data.get('t_name', '')
                            type_obj.shop = shop
                            type_obj.group_order = group_order
                            type_obj.save()
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
                                group_order=group_order
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
                        account_id = account_data.get('id')
                        acc_type_id = account_data.get('acc_type_id')
                        try:
                            acc_type = Type.objects.get(id=acc_type_id, shop=shop) if acc_type_id else None
                        except Type.DoesNotExist:
                            acc_type = None
                        
                        if account_id and Accounts.objects.filter(id=account_id).exists():
                            account_id = account_data.get('id', '').strip()
                            

                            # Update existing - use model instance to trigger history tracking
                            account = Accounts.objects.get(id=account_id)
                            account.e_name = account_data.get('e_name', '')
                            account.t_name = account_data.get('t_name', '')
                            account.shop = shop
                            account.acc_type = acc_type
                            account.priority = account_data.get('priority', 0)
                            account.is_admin_only = account_data.get('is_admin_only', False)
                            account.save()
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
                
                # Import Linked Accounts (BT_Ledger_Accounts) - After accounts are created/updated
                linked_accounts_created = 0
                linked_accounts_updated = 0
                linked_accounts_data = import_data.get('linked_accounts', [])
                
                for linked_acc_data in linked_accounts_data:
                    ledger_id = linked_acc_data.get('ledger_id')
                    account_id = linked_acc_data.get('account_id')
                    rel_type = linked_acc_data.get('rel_type')

                    if not rel_type:
                        logger.warning(f"Skipping linked account import: missing rel_type for ledger {ledger_id}")
                        continue

                    try:
                        ledger = Ledger.objects.get(id=ledger_id)
                    except Ledger.DoesNotExist:
                        logger.warning(f"Ledger {ledger_id} not found, skipping linked account import")
                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=linked_acc_data.get('id', 'unknown'),
                            record_type='BT_Ledger_Accounts',
                            status='failed',
                            message=f'Ledger {ledger_id} not found'
                        )
                        continue

                    try:
                        account = Accounts.objects.get(id=account_id)
                    except Accounts.DoesNotExist:
                        logger.warning(f"Account {account_id} not found, skipping linked account import")
                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=linked_acc_data.get('id', 'unknown'),
                            record_type='BT_Ledger_Accounts',
                            status='failed',
                            message=f'Account {account_id} not found'
                        )
                        continue

                    try:
                        with db_transaction.atomic():  # nested savepoint — isolates failures from the outer transaction
                            linked_acc, created = BT_Ledger_Accounts.objects.update_or_create(
                                ledger=ledger,
                                rel_type=rel_type,
                                defaults={
                                    'account': account,
                                    'shop': shop,
                                    'updated_by': system_user,
                                }
                            )
                            if created:
                                linked_acc.created_by = system_user
                                linked_acc.save(update_fields=['created_by'])
                                linked_accounts_created += 1
                                msg = 'Created'
                            else:
                                linked_accounts_updated += 1
                                msg = 'Updated'

                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=linked_acc.id,
                            record_type='BT_Ledger_Accounts',
                            status='success',
                            message=msg
                        )
                    except IntegrityError as e:
                        logger.error(f"Integrity error importing linked account (ledger={ledger_id}, rel_type={rel_type}): {str(e)}")
                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=linked_acc_data.get('id', 'unknown'),
                            record_type='BT_Ledger_Accounts',
                            status='failed',
                            message=f'Integrity error: {str(e)}'
                        )
                    except Exception as e:
                        logger.error(f"Error importing linked account: {str(e)}")
                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=linked_acc_data.get('id', 'unknown'),
                            record_type='BT_Ledger_Accounts',
                            status='failed',
                            message=f'Error: {str(e)}'
                        )
                
                # Import Transactions
                for trans_data in transactions_data:
                    try:
                        trans_id = trans_data.get('id', '')
                        if trans_id is not None:
                            trans_id = trans_data.get('id', '').strip()
                        account_id = trans_data.get('account_id')
                        
                        # For updates: try to get the account, but fall back to existing if not found
                        account = None
                        try:
                            account = Accounts.objects.get(id=account_id, shop=shop) if account_id else None
                        except Accounts.DoesNotExist:
                            # If it's an update and account not found, try to use existing account
                            if trans_id and Transactions.objects.filter(id=trans_id).exists():
                                existing_trans = Transactions.objects.get(id=trans_id)
                                account = existing_trans.acc
                                logger.warning(
                                    f"Account {account_id} not found for transaction {trans_id}. "
                                    f"Using existing account {existing_trans.acc_id}"
                                )
                            else:
                                account = None
                        
                        # Only raise error for new transactions without an account
                        if not account and not (trans_id and Transactions.objects.filter(id=trans_id).exists()):
                            raise ValueError(f"Account {account_id} not found for new transaction {trans_id}")
                        
                        # Parse datetime
                        trans_dt = trans_data.get('transaction_dt')
                        if isinstance(trans_dt, str):
                            trans_dt = datetime.fromisoformat(trans_dt.replace('Z', '+00:00'))
                        
                        # Convert amount to Decimal
                        amount = Decimal(str(trans_data.get('amount', 0)))
                        
                        if trans_id and Transactions.objects.filter(id=trans_id).exists():
                            # Update existing - use model instance to trigger history tracking
                            trans = Transactions.objects.get(id=trans_id)
                            # Preserve created_by, only update modified fields and set updated_by to system_user
                            if account:  # Only update account if we have one
                                trans.acc = account
                            trans.transaction_dt = trans_dt
                            trans.amount = amount
                            trans.tr_type = trans_data.get('tr_type', 'DEBIT')
                            trans.remarks = trans_data.get('remarks', '')
                            trans.is_tally = trans_data.get('is_tally', False)
                            trans.shop = shop
                            trans.loan_tr_type = trans_data.get('loan_tr_type', '')
                            # Always set updated_by to system_user, ignore any user data from import
                            trans.updated_by = system_user
                            trans.save()
                            logger.info(f"Updated transaction {trans_id}: updated_by set to {system_user.username}")
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
                            if not account:
                                raise ValueError(f"Cannot create transaction {trans_id}: Account {account_id} not found")
                            # For new transactions, always use system_user for both created_by and updated_by
                            Transactions.objects.create(
                                id=trans_id if trans_id else None,
                                acc=account,
                                transaction_dt=trans_dt,
                                amount=amount,
                                tr_type=trans_data.get('tr_type', 'DEBIT'),
                                remarks=trans_data.get('remarks', ''),
                                is_tally=trans_data.get('is_tally', False),
                                loan_tr_type=trans_data.get('loan_tr_type', ''),
                                shop=shop,
                                created_by=system_user,
                                updated_by=system_user
                            )
                            logger.info(f"Created transaction {trans_id}: created_by and updated_by set to {system_user.username}")
                            transactions_created += 1
                            manager_helper.update_account_priority(account)
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
                
                for loan_data in loans_data:
                    try:
                        loan_id    = loan_data.get('id', '').strip()
                        ledger_id  = loan_data.get('ledger_id')

                        try:
                            ledger = Ledger.objects.get(id=ledger_id)
                        except Ledger.DoesNotExist:
                            logger.warning(f"Ledger {ledger_id} not found, skipping loan {loan_id}")
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=loan_id or 'unknown',
                                record_type='Loan',
                                status='failed',
                                message=f'Ledger {ledger_id} not found'
                            )
                            continue

                        # Parse datetime
                        trans_dt = loan_data.get('transaction_dt')
                        if isinstance(trans_dt, str):
                            trans_dt = datetime.fromisoformat(trans_dt.replace('Z', '+00:00'))

                        principal = Decimal(str(loan_data.get('principal', 0)))
                        interest  = Decimal(str(loan_data.get('interest', 0)))

                        if loan_id and Loan.objects.filter(id=loan_id).exists():
                            # Update existing
                            loan_obj = Loan.objects.get(id=loan_id)
                            loan_obj.pawn_no        = loan_data.get('pawn_no', loan_obj.pawn_no)
                            loan_obj.ledger         = ledger
                            loan_obj.shop           = shop
                            loan_obj.type           = loan_data.get('type', loan_obj.type)
                            loan_obj.principal      = principal
                            loan_obj.interest       = interest
                            loan_obj.transaction_dt = trans_dt
                            loan_obj.updated_by     = system_user
                            loan_obj.save()
                            loans_updated += 1
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=loan_id,
                                record_type='Loan',
                                status='success',
                                message='Updated'
                            )
                        else:
                            # Create new
                            Loan.objects.create(
                                id=loan_id if loan_id else None,
                                pawn_no=loan_data.get('pawn_no', ''),
                                ledger=ledger,
                                shop=shop,
                                type=loan_data.get('type', 'LOAN'),
                                principal=principal,
                                interest=interest,
                                transaction_dt=trans_dt,
                                created_by=system_user,
                                updated_by=system_user,
                            )
                            loans_created += 1
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=loan_id if loan_id else 'auto',
                                record_type='Loan',
                                status='success',
                                message='Created'
                            )

                    except Exception as e:
                        logger.error(f"Error importing loan {loan_data.get('id')}: {str(e)}")
                        ImportDetails.objects.create(
                            import_history=import_history,
                            record_id=loan_data.get('id', 'unknown'),
                            record_type='Loan',
                            status='failed',
                            message=f'Error: {str(e)}'
                        )
                # ── Handle Deletions (only for incremental export modes) ─────
                if isinstance(import_data.get('types'), dict):

                    # ── Delete Types ─────────────────────────────────────────
                    for type_data in import_data.get('types', {}).get('deleted', []):
                        try:
                            type_id = type_data.get('id', '').strip()
                            if type_id and Type.objects.filter(id=type_id, shop=shop).exists():
                                Type.objects.filter(id=type_id, shop=shop).delete()
                                ImportDetails.objects.create(
                                    import_history=import_history,
                                    record_id=type_id,
                                    record_type='Type',
                                    status='success',
                                    message='Deleted'
                                )
                                logger.info(f"Deleted Type {type_id}")
                            else:
                                logger.warning(f"Type {type_id} not found for deletion — skipping")
                        except Exception as e:
                            logger.error(f"Error deleting type {type_data.get('id')}: {str(e)}")
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=type_data.get('id', 'unknown'),
                                record_type='Type',
                                status='failed',
                                message=f'Delete error: {str(e)}'
                            )

                    # ── Delete Accounts ───────────────────────────────────────
                    for account_data in import_data.get('accounts', {}).get('deleted', []):
                        try:
                            account_id = account_data.get('id', '').strip()
                            if account_id and Accounts.objects.filter(id=account_id, shop=shop).exists():
                                Accounts.objects.filter(id=account_id, shop=shop).delete()
                                ImportDetails.objects.create(
                                    import_history=import_history,
                                    record_id=account_id,
                                    record_type='Account',
                                    status='success',
                                    message='Deleted'
                                )
                                logger.info(f"Deleted Account {account_id}")
                            else:
                                logger.warning(f"Account {account_id} not found for deletion — skipping")
                        except Exception as e:
                            logger.error(f"Error deleting account {account_data.get('id')}: {str(e)}")
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=account_data.get('id', 'unknown'),
                                record_type='Account',
                                status='failed',
                                message=f'Delete error: {str(e)}'
                            )

                    # ── Delete Transactions ───────────────────────────────────
                    for trans_data in import_data.get('transactions', {}).get('deleted', []):
                        try:
                            trans_id = trans_data.get('id', '').strip()
                            if trans_id and Transactions.objects.filter(id=trans_id, shop=shop).exists():
                                Transactions.objects.filter(id=trans_id, shop=shop).delete()
                                ImportDetails.objects.create(
                                    import_history=import_history,
                                    record_id=trans_id,
                                    record_type='Transaction',
                                    status='success',
                                    message='Deleted'
                                )
                                logger.info(f"Deleted Transaction {trans_id}")
                            else:
                                logger.warning(f"Transaction {trans_id} not found for deletion — skipping")
                        except Exception as e:
                            logger.error(f"Error deleting transaction {trans_data.get('id')}: {str(e)}")
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=trans_data.get('id', 'unknown'),
                                record_type='Transaction',
                                status='failed',
                                message=f'Delete error: {str(e)}'
                            )

                    # ── Delete Loans ──────────────────────────────────────────
                    for loan_data in import_data.get('loans', {}).get('deleted', []):
                        try:
                            loan_id = loan_data.get('id', '').strip()
                            if loan_id and Loan.objects.filter(id=loan_id, shop=shop).exists():
                                Loan.objects.filter(id=loan_id, shop=shop).delete()
                                ImportDetails.objects.create(
                                    import_history=import_history,
                                    record_id=loan_id,
                                    record_type='Loan',
                                    status='success',
                                    message='Deleted'
                                )
                                logger.info(f"Deleted Loan {loan_id}")
                            else:
                                logger.warning(f"Loan {loan_id} not found for deletion — skipping")
                        except Exception as e:
                            logger.error(f"Error deleting loan {loan_data.get('id')}: {str(e)}")
                            ImportDetails.objects.create(
                                import_history=import_history,
                                record_id=loan_data.get('id', 'unknown'),
                                record_type='Loan',
                                status='failed',
                                message=f'Delete error: {str(e)}'
                            )
                # Update shop's last import timestamp
                shop.last_transaction_imported_at = timezone.now()
                shop.save(update_fields=['last_transaction_imported_at'])
                
                logger.info(
                    f"Import completed for shop {shop.id}: "
                    f"Types(C:{types_created}/U:{types_updated}), "
                    f"Accounts(C:{accounts_created}/U:{accounts_updated}), "
                    f"Linked Accounts(C:{linked_accounts_created}/U:{linked_accounts_updated}), "
                    f"Transactions(C:{transactions_created}/U:{transactions_updated}), "
                    f"Loans(C:{loans_created}/U:{loans_updated}), "
                    f"Deletions — "
                    f"Types:{_deleted_count(import_data, 'types')}, "
                    f"Accounts:{_deleted_count(import_data, 'accounts')}, "
                    f"Transactions:{_deleted_count(import_data, 'transactions')}, "
                    f"Loans:{_deleted_count(import_data, 'loans')}"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Import completed successfully',
                    'summary': {
                        'types':        {'created': types_created,        'updated': types_updated,        'deleted': _deleted_count(import_data, 'types')},
                        'accounts':     {'created': accounts_created,     'updated': accounts_updated,     'deleted': _deleted_count(import_data, 'accounts')},
                        'transactions': {'created': transactions_created, 'updated': transactions_updated, 'deleted': _deleted_count(import_data, 'transactions')},
                        'loans':        {'created': loans_created,        'updated': loans_updated,        'deleted': _deleted_count(import_data, 'loans')},
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
    
    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'manager/activity_logs.html', {
        'nav_title': 'Activity Logs',
        'selected_user': int(selected_user) if selected_user else "",
        'logs': logs,
        'users': users,
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'page_obj': page_obj,
    })

@login_required
@admin_required
def sync_grp_typ(request,pk):
    shop = Shop.objects.get(pk=pk)
    manager_helper.sync_types(request,shop)
    return redirect('manager:shop_info', pk=shop.id)

@login_required
@admin_required
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

@login_required
@admin_required
def account_info(request, pk):
    account = get_object_or_404(Accounts, pk=pk)
    fy = request.GET.get('fy')
    from_date = (request.GET.get('from_date') or '').strip()
    to_date = (request.GET.get('to_date') or '').strip()
    type_filter = request.GET.get('tr_type')
    search_query = request.GET.get('search', '')
    amount_value = request.GET.get('amount_value', '')
    amount_operator = request.GET.get('amount_operator', 'equals')
    sort_option = request.GET.get('sort', 'date_desc')
    if fy is None:
        fy = date_helper.get_current_fy_string()
    
    start_date, end_date = date_helper.get_fy_dates(fy)
    openning_balance = transaction_helper.get_account_balance(account, start_date - timedelta(microseconds=1))
    if account.acc_type.group_order == 2:
        openning_balance = 0
    # Get transactions for pagination
    transactions_qs = Transactions.objects.filter(
        acc=account,
        transaction_dt__date__gte=start_date,
        transaction_dt__date__lte=end_date,
    ).order_by('-transaction_dt')
    
    # Calculate total debit and credit
    trans_stats = transactions_qs.aggregate(
        total_debit=Sum('amount', filter=Q(tr_type='DEBIT')),
        total_credit=Sum('amount', filter=Q(tr_type='CREDIT'))
    )

    # Apply ordering based on sort option (default: date descending)
    if sort_option == 'date_asc':
        transactions_qs = transactions_qs.order_by('transaction_dt')
    else:
        transactions_qs = transactions_qs.order_by('-transaction_dt')
    

    # Apply filters
    if from_date:
        from_date_obj = date_helper.parse_date_string(from_date)
        if from_date_obj:
            from_date_dt = timezone.make_aware(
                datetime.combine(from_date_obj, datetime.min.time()),
                timezone=timezone.get_current_timezone()
            )
            transactions_qs = transactions_qs.filter(transaction_dt__gte=from_date_dt)
    
    if to_date:
        to_date_obj = date_helper.parse_date_string(to_date)
        if to_date_obj:
            to_date_dt = timezone.make_aware(
                datetime.combine(to_date_obj, datetime.max.time()),
                timezone=timezone.get_current_timezone()
            )
            transactions_qs = transactions_qs.filter(transaction_dt__lte=to_date_dt)
    
    if type_filter and type_filter in ['DEBIT', 'CREDIT']:
        transactions_qs = transactions_qs.filter(tr_type=type_filter)
    
    if amount_value:
        try:
            amount_val = Decimal(amount_value)
            if amount_operator == 'greater':
                transactions_qs = transactions_qs.filter(amount__gt=amount_val)
            elif amount_operator == 'lesser':
                transactions_qs = transactions_qs.filter(amount__lt=amount_val)
            elif amount_operator == 'equals':
                transactions_qs = transactions_qs.filter(amount=amount_val)
        except (ValueError, TypeError):
            pass
    
    if search_query:
        transactions_qs = transactions_qs.filter(remarks__icontains=search_query)

    total_debit = trans_stats['total_debit'] or Decimal('0')
    total_credit = trans_stats['total_credit'] or Decimal('0')
    closing_balance = openning_balance + total_credit - total_debit

    # Calculate total debit and credit
    trans_stats = transactions_qs.aggregate(
        total_debit=Sum('amount', filter=Q(tr_type='DEBIT')),
        total_credit=Sum('amount', filter=Q(tr_type='CREDIT'))
    )

    total_debit = trans_stats['total_debit'] or Decimal('0')
    total_credit = trans_stats['total_credit'] or Decimal('0')
    
    # Paginate transactions (10 per page)
    paginator = Paginator(transactions_qs, 10)
    page_number = request.GET.get('page', 1)
    transactions = paginator.get_page(page_number)
    
    balance = transaction_helper.get_account_balance(account)  # Calculate balance for this account
    shop_accounts = []
    for shop_account in Accounts.objects.filter(shop=account.shop).exclude(pk=account.pk).order_by('t_name'):
        group_name = 'Unknown'
        if shop_account.acc_type:
            group = manager_helper.get_group(shop_account.acc_type.group_order)
            group_name = group[2] if group else 'Unknown'
        shop_accounts.append({
            'id': shop_account.id,
            't_name': shop_account.t_name,
            'e_name': shop_account.e_name,
            'group_name': group_name,
        })
    account_group_name = manager_helper.get_group(account.acc_type.group_order)[2] if account.acc_type else 'Unknown'
    net_balance = total_credit - total_debit

    active_filter_count = sum([
        bool(from_date),
        bool(to_date),
        bool(type_filter),
        bool(search_query),
        bool(amount_value),
    ])
    has_active_filters = active_filter_count > 0

    filter_params = {'fy': fy}
    if from_date:      filter_params['from_date']        = from_date
    if to_date:        filter_params['to_date']          = to_date
    if type_filter:    filter_params['tr_type']          = type_filter
    if search_query:   filter_params['search']           = search_query
    if amount_value:
                    filter_params['amount_value']     = amount_value
                    filter_params['amount_operator']  = amount_operator
    if sort_option != 'date_desc':
                    filter_params['sort']             = sort_option

    filter_querystring = urllib.parse.urlencode(filter_params)

    return render(request, 'manager/account_info.html', {
        'nav_title': 'Shops',
        'account': account,
        'balance': balance,
        'transactions': transactions,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'shop_accounts': shop_accounts,
        'fy': fy,
        'account_group_name': account_group_name,
        'start_date': start_date,
        'end_date': end_date,
        'app_name': 'manager',
        'net_balance': net_balance,
        'opening_balance': openning_balance,
        'closing_balance': closing_balance,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'from_date': from_date,
        'to_date': to_date,
        'type_filter': type_filter,
        # 'clear_filters': clear_filters,
        'amount_value': amount_value,
        'amount_operator': amount_operator,
        'search_query': search_query,
        'sort': sort_option,
        'active_filter_count':active_filter_count,
        'has_active_filters': has_active_filters,
        'filter_querystring': filter_querystring,
    })


@login_required
@admin_required
def account_info_transactions(request, pk):
    """AJAX endpoint for HTMX to load more transactions"""
    account = get_object_or_404(Accounts, pk=pk)
    fy = request.GET.get('fy')
    from_date = (request.GET.get('from_date') or '').strip()
    to_date = (request.GET.get('to_date') or '').strip()
    type_filter = request.GET.get('tr_type')
    search_query = request.GET.get('search', '')
    amount_value = request.GET.get('amount_value', '')
    amount_operator = request.GET.get('amount_operator', 'equals')
    sort_option = request.GET.get('sort', 'date_desc')
    
    if not fy:
        fy = date_helper.get_current_fy_string()
    
    start_date, end_date = date_helper.get_fy_dates(fy)
    
    transactions_qs = Transactions.objects.filter(
        acc=account,
        transaction_dt__date__gte=start_date,
        transaction_dt__date__lte=end_date,
    ).order_by('-transaction_dt')

    # Apply ordering based on sort option (default: date descending)
    if sort_option == 'date_asc':
        transactions_qs = transactions_qs.order_by('transaction_dt')
    else:
        transactions_qs = transactions_qs.order_by('-transaction_dt')
    

    # Apply filters
    if from_date:
        from_date_obj = date_helper.parse_date_string(from_date)
        if from_date_obj:
            from_date_dt = timezone.make_aware(
                datetime.combine(from_date_obj, datetime.min.time()),
                timezone=timezone.get_current_timezone()
            )
            transactions_qs = transactions_qs.filter(transaction_dt__gte=from_date_dt)
    
    if to_date:
        to_date_obj = date_helper.parse_date_string(to_date)
        if to_date_obj:
            to_date_dt = timezone.make_aware(
                datetime.combine(to_date_obj, datetime.max.time()),
                timezone=timezone.get_current_timezone()
            )
            transactions_qs = transactions_qs.filter(transaction_dt__lte=to_date_dt)
    
    if type_filter and type_filter in ['DEBIT', 'CREDIT']:
        transactions_qs = transactions_qs.filter(tr_type=type_filter)
    
    if amount_value:
        try:
            amount_val = Decimal(amount_value)
            if amount_operator == 'greater':
                transactions_qs = transactions_qs.filter(amount__gt=amount_val)
            elif amount_operator == 'lesser':
                transactions_qs = transactions_qs.filter(amount__lt=amount_val)
            elif amount_operator == 'equals':
                transactions_qs = transactions_qs.filter(amount=amount_val)
        except (ValueError, TypeError):
            pass
    
    if search_query:
        transactions_qs = transactions_qs.filter(remarks__icontains=search_query)
    
    # Paginate transactions (10 per page)
    paginator = Paginator(transactions_qs, 10)
    page_number = request.GET.get('page', 1)
    transactions = paginator.get_page(page_number)
    shop_accounts = Accounts.objects.filter(shop=account.shop).exclude(pk=account.pk).order_by('t_name')
    
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'manager/account_transactions_partial.html', {
        'transactions': transactions,
        'account': account,
        'shop_accounts': shop_accounts,
        'fy': fy,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'filter_querystring':  params.urlencode(),
    })

@login_required
@admin_required
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
            logger.warning(f"Account deletion blocked by {request.user.username}: {account.e_name} has associated transactions")
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
def delete_transactions(request, pk):
    """Delete selected transactions for an account"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

    try:
        account = get_object_or_404(Accounts, pk=pk)
        data = json.loads(request.body)
        transaction_ids = data.get('transaction_ids', [])

        if not transaction_ids:
            return JsonResponse({'success': False, 'message': 'No transactions selected'}, status=400)

        deleted_count = 0
        skipped_count = 0
        skipped_ids = []

        with db_transaction.atomic():
            transactions = Transactions.objects.filter(id__in=transaction_ids, acc=account)
            for transaction in transactions:
                if transaction_helper.is_loan_transaction(transaction.loan_tr_type):
                    skipped_count += 1
                    skipped_ids.append(str(transaction.id))
                    continue
                manager_helper.log_activity(request, 'DELETE', 'Transaction', transaction.id, f'Transaction deleted: {transaction.remarks} ({transaction.amount} {transaction.tr_type}) for {transaction.shop.short_name}', transaction.shop)
                transaction.delete()
                deleted_count += 1

        if deleted_count == 0 and skipped_count > 0:
            return JsonResponse({'success': False, 'message': 'Selected transactions are linked to loans and cannot be deleted here. Delete them from the Loan Transactions page instead.'}, status=400)

        message = f'Successfully deleted {deleted_count} transaction(s)'
        if skipped_count:
            message += f'. {skipped_count} transaction(s) were skipped because they are loan-linked.'

        logger.info(f"Deleted {deleted_count} transactions for account {account.id} by user {request.user.username}. Skipped {skipped_count} loan-linked transaction(s).")
        return JsonResponse({'success': True, 'message': message})

    except Exception as e:
        logger.error(f"Error deleting transactions: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@admin_required
def balance_sheet(request):
    """Display group balance sheet summary for selected financial year"""
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()
    
    # Fetch all groups ordered by their order field
    groups = manager_helper.get_groups()
    
    group_summaries = []
    
    for group in groups:
        summary = transaction_helper.get_group_summary(group, fy)
        # Calculate net balance (closing - opening = credits - debits)
        net_balance = summary['closing'] - summary['opening']
        if group[0] == 2:
            summary['opening'] = Decimal('0')
        group_summaries.append({
            'id': group[0],
            'order': group[0],
            'name': group[2],
            'opening': summary['opening'],
            'closing': summary['closing'],
        })
    
    # print(group_summaries)
    net_worth_opening = group_summaries[3]['opening'] + group_summaries[4]['opening'] + group_summaries[5]['opening']
    net_worth_closing = group_summaries[3]['closing'] + group_summaries[4]['closing'] + group_summaries[5]['closing']
    cash_in_hand_opening = group_summaries[0]['opening'] + group_summaries[1]['opening'] + group_summaries[3]['opening'] + group_summaries[4]['opening'] + group_summaries[5]['opening']
    cash_in_hand_closing = group_summaries[0]['closing'] + group_summaries[1]['closing'] + group_summaries[3]['closing'] + group_summaries[4]['closing'] + group_summaries[5]['closing']

    
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

@login_required
@admin_required
def balance_sheet_shop(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()

    # ✅ Fetch all groups ordered by their order field
    groups = manager_helper.get_groups()

    grouped_list = []

    for group in groups:
        # ✅ Only types belonging to this shop AND this group
        types = Type.objects.filter(shop=shop, group_order=group[0]).order_by('e_name')

        if not types.exists():
            continue  # ✅ Skip groups with no types for this shop

        type_entries = []

        for acc_type in types:
            summary = transaction_helper.get_type_summary(acc_type, fy)
            print(f"Summary for {acc_type.e_name} (Group {group[2]}):", summary)
            if group[0] == 2:
                summary['opening'] = Decimal('0')
                summary['net_balance'] = summary['credits'] - summary['debits']
            elif group[0] == 1:
                pl_types = Type.objects.filter(shop=shop, group_order=2).order_by('e_name')
                pl_opening = Decimal('0')
                for pl_type in pl_types:
                    pl_summary = transaction_helper.get_type_summary(pl_type, str(int(fy)-1))
                    pl_opening += pl_summary['closing']
                summary['opening'] += pl_opening
                # ✅ Recompute closing AFTER opening is finalised
                summary['closing']     = summary['opening'] + summary['credits'] - summary['debits']
                summary['cur_balance'] = summary['credits'] - summary['debits']
                summary['net_balance'] = summary['opening'] + summary['cur_balance']
                
            type_entries.append({
                'id':          acc_type.id,
                'name':        acc_type.t_name,
                'e_name':      acc_type.e_name,
                'opening':     summary['opening'],
                'credits':     summary['credits'],
                'debits':      summary['debits'],
                'closing':     summary['closing'],
                'net_balance': summary['net_balance'],
                'cur_balance': summary['cur_balance'],
            })

        grouped_list.append({
            'group_id':          group[0],
            'group_name':        group[2],
            'group_order':       group[0],
            'types':             type_entries,
        })
    _, fy_end_date = date_helper.get_fy_dates(fy)
    cash_in_hand = transaction_helper.get_opening_balance(shop, fy_end_date.date())
    ledgers = Ledger.objects.filter(shop=shop).order_by('name')
    balance = transaction_helper.get_balance(shop)  # Calculate balance from transactions for accuracy
    return render(request, 'manager/balance_sheet_shop.html', {
        'nav_title':      'Shops',
        'fy':             fy,
        'shop':           shop,
        'grouped_list':   grouped_list,  # ✅ replaces 'items'
        'app_name':       'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin':       is_admin(request.user),
        'cash_in_hand': cash_in_hand['closing_balance'],
        'ledgers': ledgers,
        'balance': balance,
    })

@login_required
@admin_required
def close_pl_accounts(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy')
    base_url = reverse('manager:close-pl-accounts', kwargs={'pk': pk})
    
    if fy is None:
        fy = date_helper.get_current_fy_string()

    pl_accounts = Accounts.objects.filter(
        shop=shop,
        acc_type__group_order=2
    )
    pl_account_balances = []
    total = 0

    capital_accounts = Accounts.objects.filter(
        shop=shop,
        acc_type__group_order=1
    )

    for account in pl_accounts:
        summary = transaction_helper.get_account_summary(account, fy)
        if summary['net_balance'] > 0 or summary['net_balance'] < 0:
            pl_account_balances.append({
                'id':      account.id,
                'name':    account.t_name,
                'type': account.acc_type,
                'opening': summary['opening'],
                'credits': abs(summary['credits']),
                'debits':  abs(summary['debits']),
                'closing': summary['closing'],
                'net_balance': summary['net_balance'],
                'cur_balance': summary['cur_balance'],
            })
            total = total + summary['net_balance']
    
    capital_accounts_count = capital_accounts.count()
    each_share = round(total/capital_accounts_count,2)

    if request.method == 'POST':
        capital_amounts = {}
        entered_total = Decimal('0')

        for key, value in request.POST.items():
            if key.startswith('amount_'):
                acc_id = key.replace('amount_', '')
                amount = Decimal(value or '0')
                capital_amounts[acc_id] = amount
                entered_total += amount
                print(f"ammount['{acc_id}']: {amount}")
        total = Decimal(total)
        if round(entered_total, 2) != round(total, 2):
            messages.error(request, f"Entered amounts do not match the expected total. Actual total: {entered_total}, Expected total: {total}")
            return redirect(f"{base_url}?fy={fy}")

        try:
            with db_transaction.atomic():
                print(fy)
                print(date_helper.get_current_fy_string())
                if fy is None or fy == date_helper.get_current_fy_string():
                    tr_date = timezone.localdate()
                else:
                    tr_date = date_helper.get_fy_last_date(fy)
                for account in pl_account_balances:
                    acc = Accounts.objects.get(id=account['id'])
                    print(f"{acc}: {account['net_balance']}")
                    if (account['net_balance']) > 0:
                        transaction_helper.create_transaction(
                            shop,abs(account['net_balance']),'DEBIT','Transferred to Capital Account',
                            None,tr_date,request.user,acc,''
                        )
                        logger.info(f"Rs.{account['net_balance']} has been debited from {acc.e_name}")
                    elif (account['net_balance']) < 0:
                        transaction_helper.create_transaction(
                            shop,abs(account['net_balance']),'CREDIT','Transferred to Capital Account',
                            None,tr_date,request.user,acc,''
                        )
                        logger.info(f"Rs.{-account['net_balance']} has been credited to {acc.e_name}")
                
                for acc_id, amount in capital_amounts.items():
                    acc = Accounts.objects.get(id=acc_id)
                    if amount > 0:
                        transaction_helper.create_transaction(
                            shop,amount,'CREDIT','Credited from PL Account',
                            None,tr_date,request.user,acc,''
                        )
                        logger.info(f"Rs.{amount} has been credited to {acc.e_name}")
                    elif amount < 0:
                        transaction_helper.create_transaction(
                            shop,abs(amount),'DEBIT','Debited to PL Account',
                            None,tr_date,request.user,acc,''
                        )
                        logger.info(f"Rs.{amount} has been debited from {acc.e_name}")
            messages.success(request,"Funds are transferred/debited from PL accounts to capital accounts")
            return redirect(f"{base_url}?fy={fy}")
        except Exception as e:  
            messages.error(request, f"Unable to process request! due to: {e}")
            print(e)
            return redirect(f"{base_url}?fy={fy}")
    
    ledgers = Ledger.objects.filter(shop=shop).order_by('name')
    balance = transaction_helper.get_balance(shop)  # Calculate balance from transactions for accuracy
    return render(request, 'manager/close_pl_accounts.html', {
        'nav_title': 'Shops',
        'fy': fy,
        'shop': shop,
        'items': pl_account_balances,
        'item_type': 'Account',
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'total': total,
        'each_share': each_share,
        'capital_accounts': capital_accounts,
        'capital_accounts_count': capital_accounts_count,
        'fy':fy,
        'ledgers': ledgers,
        'balance': balance,
    })

@login_required
@admin_required
def account_balance_sheet(request, pk, type_pk):
    shop = Shop.objects.get(pk=pk)
    type_obj = get_object_or_404(Type, pk=type_pk, shop=shop)

    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_type_info':
            type_obj.e_name = request.POST.get('e_name', '').strip()
            type_obj.t_name = request.POST.get('t_name', '').strip()
            type_obj.save(update_fields=['e_name', 't_name'])
            messages.success(request, 'Type details updated successfully.')
            return redirect(f"{reverse('manager:type_balance_sheet', kwargs={'pk': shop.pk, 'type_pk': type_obj.pk})}?fy={fy}")

        messages.error(request, 'Invalid request.')
        return redirect(f"{reverse('manager:type_balance_sheet', kwargs={'pk': shop.pk, 'type_pk': type_obj.pk})}?fy={fy}")

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

    overall_balance = sum((item['net_balance'] for item in account_balances), Decimal('0'))

    return render(request, 'manager/summary_account.html', {
        'nav_title': 'Shops',
        'fy': fy,
        'shop': shop,
        'type_e_name': type_obj.e_name,
        'type_t_name': type_obj.t_name,
        'items': account_balances,
        'item_type': 'Account',
        'app_name': 'manager',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'group_name': manager_helper.get_group(type_obj.group_order)[2],
        'overall_balance': overall_balance,
    })

@login_required
@admin_required
def link_ledger_accounts(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

    try:
        data = json.loads(request.body)
        ledger = get_object_or_404(Ledger, pk=pk)

        account_types = {
            'Loan Principal Account': 'LOAN_PRINCIPAL',
            'Loan Interest Account': 'LOAN_INTEREST',
            'Release Principal Account': 'RELEASE_PRINCIPAL',
            'Release Interest Account': 'RELEASE_INTEREST',
        }

        created_count = 0
        updated_count = 0

        with db_transaction.atomic():
            for display_name, rel_type in account_types.items():
                account_id = data.get(rel_type)
                if not account_id:
                    continue

                account = get_object_or_404(Accounts, pk=account_id)

                bt_ledger_account, created = BT_Ledger_Accounts.objects.update_or_create(
                    ledger=ledger,
                    rel_type=rel_type,
                    defaults={
                        'shop': ledger.shop,
                        'account': account,
                        'updated_by': request.user,
                    }
                )

                if created:
                    bt_ledger_account.created_by = request.user
                    bt_ledger_account.save(update_fields=['created_by'])
                    created_count += 1
                    manager_helper.log_activity(
                        request, 'CREATE', 'BT_Ledger_Accounts', bt_ledger_account.id,
                        f'Created {display_name} ({account.e_name}) for ledger {ledger.name}',
                        ledger.shop
                    )
                else:
                    updated_count += 1
                    manager_helper.log_activity(
                        request, 'UPDATE', 'BT_Ledger_Accounts', bt_ledger_account.id,
                        f'Updated {display_name} to {account.e_name} for ledger {ledger.name}',
                        ledger.shop
                    )

        message = f'Linked accounts saved successfully! ({created_count} created, {updated_count} updated)'
        logger.info(f"Ledger accounts linked by {request.user.username}: {ledger.name}, created: {created_count}, updated: {updated_count}")

        return JsonResponse({
            'success': True,
            'message': message,
            'created': created_count,
            'updated': updated_count,
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    except Ledger.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Ledger not found'}, status=404)
    except Accounts.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'One or more selected accounts not found'}, status=404)
    except IntegrityError:
        return JsonResponse({'success': False, 'message': 'A duplicate linkage was detected — please refresh and try again'}, status=409)
    except Exception as e:
        logger.error(f"Error linking ledger accounts by {request.user.username}: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An error occurred while saving linked accounts'}, status=500)

@login_required
@admin_required
def trial_balance_pdf(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()

    types = Type.objects.filter(shop=shop)
    rows = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for acc_type in types:
        summary = transaction_helper.get_type_summary(acc_type, fy)
        closing = summary['closing']
        opening = summary['opening']
        if acc_type.group_order == 2:  # For PL accounts, opening balance is considered as zero
            opening = Decimal('0.00')
        if closing > 0:
            rows.append({'name': acc_type.t_name, 'debit': '', 'credit': closing})
            total_credit += closing
        elif closing < 0:
            rows.append({'name': acc_type.t_name, 'debit': opening, 'credit': ''})
            total_debit += opening

    context = {
        'shop': shop,
        'fy': fy,
        'rows': rows,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'nav_title': f'Trial Balance - {shop.short_name}',
        'app_name': 'manager',
    }
    return render(request, 'manager/trial_balance_print.html', context)

@login_required
@admin_required
def trial_balance_wopl_pdf(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()

    types = Type.objects.filter(shop=shop)
    rows = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for acc_type in types:
        if acc_type.group_order == 2:  # Skip Loan Accounts
            continue
        summary = transaction_helper.get_type_summary(acc_type, fy)
        closing = summary['closing']
        opening = summary['opening']
        if acc_type.group_order == 2:  # For PL accounts, opening balance is considered as zero
            opening = Decimal('0.00')
        if closing > 0:
            rows.append({'name': acc_type.t_name, 'debit': '', 'credit': closing})
            total_credit += closing
        elif closing < 0:
            rows.append({'name': acc_type.t_name, 'debit': opening, 'credit': ''})
            total_debit += opening

    context = {
        'shop': shop,
        'fy': fy,
        'rows': rows,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'nav_title': f'Trial Balance - {shop.short_name}',
        'app_name': 'manager',
    }
    return render(request, 'manager/trial_balance_print.html', context)

@login_required
@admin_required
def _zero_pl_openings(group_fy_data):
    """Zero out opening balances for all types/accounts in group_order 2 (PL)."""
    for group in group_fy_data:
        if group['id'] == 2:
            for acc_type in group['types']:
                acc_type['opening'] = 0
                for acc in acc_type['accounts']:
                    acc['opening'] = 0
            group['opening'] = 0

@login_required
@admin_required
def _filter_empty(group_fy_data):
    """Remove zero-closing accounts from all groups, then remove types with no accounts."""
    for group in group_fy_data:
        for acc_type in group['types']:
            acc_type['accounts'] = [a for a in acc_type['accounts'] if a['closing'] != 0]
        group['types'] = [t for t in group['types'] if t['accounts']]

@login_required
@admin_required
def bs_shop_pdf(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()

    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _zero_pl_openings(group_fy_data)
    _filter_empty(group_fy_data)
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)

    context = {
        'shop': shop,
        'fy': fy,
        'group_fy_data': group_fy_data,
        'total_opening': total_opening,
        'total_closing': total_closing,
        'nav_title': f'Balance Sheet - {shop.short_name}',
    }
    return render(request, 'manager/bs_shop_print.html', context)

@login_required
@admin_required
def bs_shop_wo_pl_pdf(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()

    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _filter_empty(group_fy_data)
    # Exclude group_order 2 (PL)
    group_fy_data = [g for g in group_fy_data if g['id'] != 2]
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)

    context = {
        'shop': shop,
        'fy': fy,
        'group_fy_data': group_fy_data,
        'total_opening': total_opening,
        'total_closing': total_closing,
        'nav_title': f'Balance Sheet (W/O P&L) - {shop.short_name}',
        'app_name': 'manager',
    }
    return render(request, 'manager/bs_shop_print.html', context)


@login_required
@admin_required
def _filter_empty_types(group_fy_data):
    """Remove zero-closing types from all groups."""
    for group in group_fy_data:
        group['types'] = [t for t in group['types'] if t['closing'] != 0]


@login_required
@admin_required
def group_type_summary_pdf(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy')
    if fy is None:
        fy = date_helper.get_current_fy_string()

    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _zero_pl_openings(group_fy_data)
    _filter_empty_types(group_fy_data)
    # Remove groups with no types after filtering
    group_fy_data = [g for g in group_fy_data if g['types']]
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)

    context = {
        'shop': shop,
        'fy': fy,
        'group_fy_data': group_fy_data,
        'total_opening': total_opening,
        'total_closing': total_closing,
        'nav_title': f'Group & Type Summary - {shop.short_name}',
        'app_name': 'manager',
    }
    return render(request, 'manager/group_type_summary_print.html', context)


@login_required
@admin_required
def shops_yearly_summary_pdf(request):
    """
    Pivot report: rows = available FY years, columns = each shop + Total.
    Net worth per cell = group_closing[2] + group_closing[3] + group_closing[4]
    (same formula as networth_chart_data in api/views.py, scoped per shop).
    """
    NETWORTH_GROUPS = [3, 4, 5]  # PL, Purchases, Liabilities

    shops = list(Shop.objects.all().order_by('short_name'))
    fys = date_helper.get_available_fy_years()

    decimal_mask = Decimal('0.01')

    def _shop_group_closing(shop, group_order, start_date, end_date):
        """Closing balance for one shop + group_order in a given FY."""
        opening_agg = Transactions.objects.filter(
            shop=shop,
            acc__acc_type__group_order=group_order,
            transaction_dt__date__lt=start_date,
        ).aggregate(
            c=Sum('amount', filter=Q(tr_type='CREDIT')),
            d=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
        opening = (opening_agg['c'] or Decimal('0')) - (opening_agg['d'] or Decimal('0'))
        if group_order == 2:
            opening = Decimal('0')  # PL opening always zero

        fy_agg = Transactions.objects.filter(
            shop=shop,
            acc__acc_type__group_order=group_order,
            transaction_dt__date__gte=start_date,
            transaction_dt__date__lte=end_date,
        ).aggregate(
            c=Sum('amount', filter=Q(tr_type='CREDIT')),
            d=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
        credits = fy_agg['c'] or Decimal('0')
        debits  = fy_agg['d'] or Decimal('0')
        return opening + credits - debits

    rows = []
    col_totals = [Decimal('0.00')] * len(shops)
    grand_total = Decimal('0.00')

    for fy in fys:
        start_date, end_date = date_helper.get_fy_dates(fy)
        fy_int = int(fy)
        fy_label = f'{fy_int}-{str(fy_int + 1)[2:]}'

        shop_networths = []
        row_total = Decimal('0.00')

        for idx, shop in enumerate(shops):
            net_worth = sum(
                _shop_group_closing(shop, g, start_date, end_date)
                for g in NETWORTH_GROUPS
            ).quantize(decimal_mask, rounding=ROUND_HALF_UP)
            shop_networths.append(net_worth)
            row_total += net_worth
            col_totals[idx] += net_worth

        row_total = row_total.quantize(decimal_mask, rounding=ROUND_HALF_UP)
        grand_total += row_total
        rows.append({'fy_label': fy_label, 'closings': shop_networths, 'total': row_total})

    col_totals = [v.quantize(decimal_mask, rounding=ROUND_HALF_UP) for v in col_totals]
    grand_total = grand_total.quantize(decimal_mask, rounding=ROUND_HALF_UP)

    context = {
        'shops': shops,
        'rows': rows,
        'col_totals': col_totals,
        'grand_total': grand_total,
        'nav_title': 'Networth Summary',
        'app_name': 'manager',
    }
    return render(request, 'manager/networth_summary.html', context)


# ──────────────────────────────────────────────────────────────
# Excel / CSV exports
# ──────────────────────────────────────────────────────────────

@login_required
@admin_required
def _build_trial_balance_rows(shop, fy, skip_pl=False):
    """Shared data preparation for trial-balance export views."""
    types = Type.objects.filter(shop=shop)
    rows = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for acc_type in types:
        if skip_pl and acc_type.group_order == 2:
            continue
        summary = transaction_helper.get_type_summary(acc_type, fy)
        closing = summary['closing']
        opening = summary['opening']
        if acc_type.group_order == 2:  # For PL accounts, opening balance is considered as zero
            opening = Decimal('0.00')
        if closing > 0:
            rows.append({'name': acc_type.t_name, 'debit': '', 'credit': closing})
            total_credit += closing
        elif closing < 0:
            rows.append({'name': acc_type.t_name, 'debit': opening, 'credit': ''})
            total_debit += opening
    return rows, total_debit, total_credit


@login_required
@admin_required
def trial_balance_excel(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    rows, total_debit, total_credit = _build_trial_balance_rows(shop, fy, skip_pl=False)
    title = f'Trial Balance - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_trial_balance_table(rows, total_debit, total_credit)
    excel_buffer = report_helper.generate_excel_report(title, table_data)
    response = HttpResponse(excel_buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="trial_balance_{shop.short_name}_{fy}.xlsx"'
    return response


@login_required
@admin_required
def trial_balance_csv(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    rows, total_debit, total_credit = _build_trial_balance_rows(shop, fy, skip_pl=False)
    title = f'Trial Balance - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_trial_balance_table(rows, total_debit, total_credit)
    csv_buffer = report_helper.generate_csv_report(title, table_data)
    response = HttpResponse(csv_buffer.read(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="trial_balance_{shop.short_name}_{fy}.csv"'
    return response


@login_required
@admin_required
def trial_balance_wopl_excel(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    rows, total_debit, total_credit = _build_trial_balance_rows(shop, fy, skip_pl=True)
    title = f'Trial Balance (W/O P&L) - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_trial_balance_table(rows, total_debit, total_credit)
    excel_buffer = report_helper.generate_excel_report(title, table_data)
    response = HttpResponse(excel_buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="trial_balance_wopl_{shop.short_name}_{fy}.xlsx"'
    return response


@login_required
@admin_required
def trial_balance_wopl_csv(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    rows, total_debit, total_credit = _build_trial_balance_rows(shop, fy, skip_pl=True)
    title = f'Trial Balance (W/O P&L) - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_trial_balance_table(rows, total_debit, total_credit)
    csv_buffer = report_helper.generate_csv_report(title, table_data)
    response = HttpResponse(csv_buffer.read(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="trial_balance_wopl_{shop.short_name}_{fy}.csv"'
    return response


@login_required
@admin_required
def bs_shop_excel(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _zero_pl_openings(group_fy_data)
    _filter_empty(group_fy_data)
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)
    title = f'Balance Sheet - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_bs_shop_table(group_fy_data, total_opening, total_closing)
    excel_buffer = report_helper.generate_excel_report(title, table_data)
    response = HttpResponse(excel_buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="balance_sheet_{shop.short_name}_{fy}.xlsx"'
    return response


@login_required
@admin_required
def bs_shop_csv(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _zero_pl_openings(group_fy_data)
    _filter_empty(group_fy_data)
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)
    title = f'Balance Sheet - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_bs_shop_table(group_fy_data, total_opening, total_closing)
    csv_buffer = report_helper.generate_csv_report(title, table_data)
    response = HttpResponse(csv_buffer.read(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="balance_sheet_{shop.short_name}_{fy}.csv"'
    return response


@login_required
@admin_required
def bs_shop_wo_pl_excel(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _filter_empty(group_fy_data)
    group_fy_data = [g for g in group_fy_data if g['id'] != 2]
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)
    title = f'Balance Sheet (W/O P&L) - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_bs_shop_table(group_fy_data, total_opening, total_closing)
    excel_buffer = report_helper.generate_excel_report(title, table_data)
    response = HttpResponse(excel_buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="balance_sheet_wopl_{shop.short_name}_{fy}.xlsx"'
    return response


@login_required
@admin_required
def bs_shop_wo_pl_csv(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _filter_empty(group_fy_data)
    group_fy_data = [g for g in group_fy_data if g['id'] != 2]
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)
    title = f'Balance Sheet (W/O P&L) - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_bs_shop_table(group_fy_data, total_opening, total_closing)
    csv_buffer = report_helper.generate_csv_report(title, table_data)
    response = HttpResponse(csv_buffer.read(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="balance_sheet_wopl_{shop.short_name}_{fy}.csv"'
    return response


@login_required
@admin_required
def group_type_summary_excel(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _zero_pl_openings(group_fy_data)
    _filter_empty_types(group_fy_data)
    group_fy_data = [g for g in group_fy_data if g['types']]
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)
    title = f'Group & Type Summary - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_group_type_summary_table(group_fy_data, total_opening, total_closing)
    excel_buffer = report_helper.generate_excel_report(title, table_data)
    response = HttpResponse(excel_buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="group_type_summary_{shop.short_name}_{fy}.xlsx"'
    return response


@login_required
@admin_required
def group_type_summary_csv(request, pk):
    shop = Shop.objects.get(pk=pk)
    fy = request.GET.get('fy') or date_helper.get_current_fy_string()
    group_fy_data = transaction_helper.group_fy_data(shop, fy)
    _zero_pl_openings(group_fy_data)
    _filter_empty_types(group_fy_data)
    group_fy_data = [g for g in group_fy_data if g['types']]
    total_opening = sum(g['opening'] for g in group_fy_data)
    total_closing = sum(g['closing'] for g in group_fy_data)
    title = f'Group & Type Summary - {shop.short_name} - FY{fy}'
    table_data = report_helper.build_group_type_summary_table(group_fy_data, total_opening, total_closing)
    csv_buffer = report_helper.generate_csv_report(title, table_data)
    response = HttpResponse(csv_buffer.read(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="group_type_summary_{shop.short_name}_{fy}.csv"'
    return response


@login_required
@admin_required
def shops_yearly_summary_excel(request):
    NETWORTH_GROUPS = [2, 3, 4]
    shops = list(Shop.objects.all().order_by('short_name'))
    fys = date_helper.get_available_fy_years()
    decimal_mask = Decimal('0.01')

    def _shop_group_closing(shop, group_order, start_date, end_date):
        opening_agg = Transactions.objects.filter(
            shop=shop,
            acc__acc_type__group_order=group_order,
            transaction_dt__date__lt=start_date,
        ).aggregate(
            c=Sum('amount', filter=Q(tr_type='CREDIT')),
            d=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
        opening = (opening_agg['c'] or Decimal('0')) - (opening_agg['d'] or Decimal('0'))
        if group_order == 2:
            opening = Decimal('0')
        fy_agg = Transactions.objects.filter(
            shop=shop,
            acc__acc_type__group_order=group_order,
            transaction_dt__date__gte=start_date,
            transaction_dt__date__lte=end_date,
        ).aggregate(
            c=Sum('amount', filter=Q(tr_type='CREDIT')),
            d=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
        credits = fy_agg['c'] or Decimal('0')
        debits  = fy_agg['d'] or Decimal('0')
        return opening + credits - debits

    rows = []
    col_totals = [Decimal('0.00')] * len(shops)
    grand_total = Decimal('0.00')
    for fy in fys:
        start_date, end_date = date_helper.get_fy_dates(fy)
        fy_int = int(fy)
        fy_label = f'{fy_int}-{str(fy_int + 1)[2:]}'
        shop_networths = []
        row_total = Decimal('0.00')
        for idx, shop in enumerate(shops):
            net_worth = sum(
                _shop_group_closing(shop, g, start_date, end_date)
                for g in NETWORTH_GROUPS
            ).quantize(decimal_mask, rounding=ROUND_HALF_UP)
            shop_networths.append(net_worth)
            row_total += net_worth
            col_totals[idx] += net_worth
        row_total = row_total.quantize(decimal_mask, rounding=ROUND_HALF_UP)
        grand_total += row_total
        rows.append({'fy_label': fy_label, 'closings': shop_networths, 'total': row_total})
    col_totals = [v.quantize(decimal_mask, rounding=ROUND_HALF_UP) for v in col_totals]
    grand_total = grand_total.quantize(decimal_mask, rounding=ROUND_HALF_UP)

    table_data = report_helper.build_networth_summary_table(shops, rows)
    excel_buffer = report_helper.generate_excel_report('Networth Summary', table_data)
    response = HttpResponse(excel_buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="networth_summary.xlsx"'
    return response


@login_required
@admin_required
def shops_yearly_summary_csv(request):
    NETWORTH_GROUPS = [2, 3, 4]
    shops = list(Shop.objects.all().order_by('short_name'))
    fys = date_helper.get_available_fy_years()
    decimal_mask = Decimal('0.01')

    def _shop_group_closing(shop, group_order, start_date, end_date):
        opening_agg = Transactions.objects.filter(
            shop=shop,
            acc__acc_type__group_order=group_order,
            transaction_dt__date__lt=start_date,
        ).aggregate(
            c=Sum('amount', filter=Q(tr_type='CREDIT')),
            d=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
        opening = (opening_agg['c'] or Decimal('0')) - (opening_agg['d'] or Decimal('0'))
        if group_order == 2:
            opening = Decimal('0')
        fy_agg = Transactions.objects.filter(
            shop=shop,
            acc__acc_type__group_order=group_order,
            transaction_dt__date__gte=start_date,
            transaction_dt__date__lte=end_date,
        ).aggregate(
            c=Sum('amount', filter=Q(tr_type='CREDIT')),
            d=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
        credits = fy_agg['c'] or Decimal('0')
        debits  = fy_agg['d'] or Decimal('0')
        return opening + credits - debits

    rows = []
    col_totals = [Decimal('0.00')] * len(shops)
    grand_total = Decimal('0.00')
    for fy in fys:
        start_date, end_date = date_helper.get_fy_dates(fy)
        fy_int = int(fy)
        fy_label = f'{fy_int}-{str(fy_int + 1)[2:]}'
        shop_networths = []
        row_total = Decimal('0.00')
        for idx, shop in enumerate(shops):
            net_worth = sum(
                _shop_group_closing(shop, g, start_date, end_date)
                for g in NETWORTH_GROUPS
            ).quantize(decimal_mask, rounding=ROUND_HALF_UP)
            shop_networths.append(net_worth)
            row_total += net_worth
            col_totals[idx] += net_worth
        row_total = row_total.quantize(decimal_mask, rounding=ROUND_HALF_UP)
        grand_total += row_total
        rows.append({'fy_label': fy_label, 'closings': shop_networths, 'total': row_total})

    table_data = report_helper.build_networth_summary_table(shops, rows)
    csv_buffer = report_helper.generate_csv_report('Networth Summary', table_data)
    response = HttpResponse(csv_buffer.read(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="networth_summary.csv"'
    return response

def download_backup(request):
    db_path = settings.DATABASES['default']['NAME']
    timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    filename = f'daybook_backup_{timestamp}.sqlite3'
    with open(db_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response