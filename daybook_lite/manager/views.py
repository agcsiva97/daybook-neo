import logging
from pyexpat.errors import messages

from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

from .helper import manager_helper
from .forms import LedgerForm, ShopForm, ShopEditForm
from django.core.paginator import Paginator
from django.contrib.auth import  get_user_model

from entries.views import admin_required, super_admin_required, is_admin
from .models import Configuration, Shop, ActivityLog, Ledger
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
            balance = form.cleaned_data.get('balance')
            try:
                with db_transaction.atomic():
                    shop = manager_helper.create_shop(short_name, name, d_no, addressline1, addressline2, place, pincode, balance)
                    if shop is not None:
                        print(f"Shop created with ID: {shop.id}")
                        manager_helper.create_ledger(shop.short_name, "", shop)
                        transaction_helper.create_transaction(
                            shop=shop,
                            amount=shop.balance,
                            tr_type='CREDIT',
                            name='Opening Deposit',
                            remarks='Account Opening Deposit',
                            old_balance=0,
                            chosen_dt=timezone.now(),
                            user=request.user
                        )
                        # logger.info(f"Shop created by {request.user.username}: {shop.id}")
                        messages.success(request, f'Shop "{shop.short_name}" created successfully!')
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
    transactions_list = Transactions.objects.filter(shop=shop).order_by('-transaction_dt')[:10]
    
    return render(request, 'manager/shop_info.html', {
        'nav_title': 'Shops',
        'shop': shop,
        'ledgers': ledgers,
        'transactions_list': transactions_list,
        'balance': balance,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'app_name': 'manager',
    })


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
    })

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
    })