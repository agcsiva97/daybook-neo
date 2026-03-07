from datetime import datetime, time as dt_time
from decimal import Decimal
import csv
import logging
import openpyxl
from functools import wraps
from openpyxl.styles import Font, Alignment, PatternFill

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction as db_transaction
from django.db.models import Case, DecimalField, F, Min, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import LedgerForm, ShopForm, ShopEditForm, TransactionForm, TransferForm, DenominationForm, LoanForm, LoanEditForm
from .models import Transactions, Ledger, Denomination, Loan, Shop
from .helpers import transactions as transaction_helper

logger = logging.getLogger(__name__)


def is_admin(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists()

def is_super_admin(user):
    return user.is_superuser

def is_admin_or_staff(user):
    return user.is_superuser or user.groups.filter(name__in=['Admin', 'Staff']).exists()


# Custom decorators that raise PermissionDenied instead of redirecting to login
def admin_required(view_func):
    """Decorator that requires user to be admin or superuser. Shows 403 if not."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied('You do not have permission to access this page.')
        return view_func(request, *args, **kwargs)
    return wrapper

def super_admin_required(view_func):
    """Decorator that requires user to be superuser. Shows 403 if not."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_super_admin(request.user):
            raise PermissionDenied('You do not have permission to access this page.')
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_or_staff_required(view_func):
    """Decorator that requires user to be admin, staff, or superuser. Shows 403 if not."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin_or_staff(request.user):
            raise PermissionDenied('You do not have permission to access this page.')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@admin_required
def dashboard(request):
    from entries.models import Shop
    shops = Shop.objects.all().order_by('short_name')
    return render(request, 'entries/dashboard.html', {'nav_title': 'Dashboard', 'shops': shops})


@login_required
@super_admin_required
def add_shop(request):
    if request.method == 'POST':
        form = ShopForm(request.POST)
        if form.is_valid():
            try:
                shop = form.save()
                logger.info(f"Shop created by {request.user.username}: {shop.id}")
                messages.success(request, f'Shop "{shop.name}" created successfully!')
                return redirect('entries:home')
            except Exception as e:
                logger.error(f"Error creating shop by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while creating shop.')
    else:
        form = ShopForm()
    return render(request, 'entries/add_shop.html', {'nav_title': 'Shops', 'form': form})


@login_required
@admin_required
def shop_info(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    ledgers = Ledger.objects.filter(shop=shop).order_by('name')
    
    # Get all transactions for this shop
    transactions_list = Transactions.objects.filter(shop=shop).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(transactions_list, 25)  # Show 25 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'entries/shop_info.html', {
        'nav_title': 'Shops',
        'shop': shop,
        'ledgers': ledgers,
        'page_obj': page_obj,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
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
                return redirect('entries:shop_info', pk=shop.pk)
            except Exception as e:
                logger.error(f"Error editing shop {pk} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while updating shop.')
    else:
        form = ShopEditForm(instance=shop)
    return render(request, 'entries/edit_shop.html', {'nav_title': 'Shops', 'form': form, 'shop': shop})


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
            return redirect('entries:shop_info', pk=shop.pk)
        shop_name = shop.name
        try:
            shop.delete()
            logger.warning(f"Shop deleted by {request.user.username}: {shop_name}")
            messages.success(request, f'Shop "{shop_name}" deleted successfully!')
        except Exception as e:
            logger.error(f"Error deleting shop {shop_name} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting shop.')
            return redirect('entries:shop_info', pk=pk)
        return redirect('entries:home')
    return render(request, 'entries/delete_shop.html', {'nav_title': 'Shops', 'shop': shop})


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

                    # Note: Opening balance feature removed - ledger balance field removed from model
                    # Shop balance is now managed independently through transactions
                    if False:  # Disabled opening balance logic
                        # Lock the shop for balance update
                        shop = Shop.objects.select_for_update().get(pk=shop_pk)
                        old_shop_balance = shop.balance
                        new_shop_balance = old_shop_balance + opening_balance
                        Transactions.objects.create(
                            amount=opening_balance,
                            shop=shop,
                            tr_type='CREDIT',
                            remarks='Account Opening Deposit',
                            old_balance=old_shop_balance,
                            new_balance=new_shop_balance,
                            created_by=request.user,
                            updated_by=request.user
                        )
                        shop.balance = new_shop_balance
                        shop.save()

                        logger.info(f"Ledger created by {request.user.username}: name={ledger.name}, shop={shop.name}, opening balance={opening_balance}")
                    else:
                        logger.info(f"Ledger created by {request.user.username}: name={ledger.name}, shop={shop.name}, balance=0")

                messages.success(request, f'Ledger "{ledger.name}" created for shop "{shop.name}"!')
                return redirect('entries:shop_info', pk=shop.pk)
            except Exception as e:
                logger.error(f"Error creating ledger for shop {shop.name} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while creating ledger.')
    else:
        form = LedgerForm()

    return render(request, 'entries/add_shop_ledger.html', {
        'nav_title': 'Shops',
        'form': form,
        'shop': shop,
    })


@login_required
def home(request):
    today = timezone.localdate()
    transactions = Transactions.objects.filter(created_at__date=today).order_by('-created_at')[:10]
    daily_totals = (
        Transactions.objects.filter(created_at__date=today)
        .values('shop_id')
        .annotate(
            debit_total=Coalesce(
                Sum(
                    Case(
                        When(tr_type='DEBIT', then=F('amount')),
                        default=Value(0),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            credit_total=Coalesce(
                Sum(
                    Case(
                        When(tr_type='CREDIT', then=F('amount')),
                        default=Value(0),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
    )
    totals_by_shop = {item['shop_id']: item for item in daily_totals}
    shops = Shop.objects.all().order_by('name')
    
    # Calculate opening and closing balance for each shop
    shop_balances = []
    for shop in shops:
        # Get first transaction of today for this shop to get opening balance
        first_transaction_today = Transactions.objects.filter(
            shop=shop,
            created_at__date=today
        ).order_by('created_at').first()
        
        if first_transaction_today and first_transaction_today.old_balance is not None:
            opening_balance = first_transaction_today.old_balance
        else:
            # No transactions today, opening balance is current balance
            opening_balance = shop.balance
        
        closing_balance = shop.balance
        
        shop_balances.append({
            'shop': shop,
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
        })
    
    context = {
        'nav_title':'Home',
        'transactions': transactions,
        'shop_balances': shop_balances,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    
    return render(request, 'entries/home.html',context)


@login_required
def add_entries(request):
    form = TransactionForm()
    transfer_form = TransferForm()
    loan_form = LoanForm()
    
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            
            if request.user.is_authenticated:
                transaction.created_by = request.user
                transaction.updated_by = request.user
            
            # Apply chosen date+time to created_at
            chosen_date = form.cleaned_data.get('date')
            if chosen_date:
                chosen_time = form.cleaned_data.get('time') or timezone.localtime(timezone.now()).time()
                transaction.created_at = timezone.make_aware(
                    datetime.combine(chosen_date, chosen_time)
                )

            try:
                with db_transaction.atomic():
                    # Lock the shop row to prevent race conditions
                    shop = Shop.objects.select_for_update().get(pk=transaction.shop_id)
                    
                    # Get the previous transaction to chain balances
                    latest_previous_transaction = (
                        Transactions.objects.filter(
                            shop_id=transaction.shop_id,
                            created_at__lt=transaction.created_at,
                        )
                        .order_by('-created_at')
                        .first()
                    )
                    
                    # Get old_balance from previous transaction's new_balance
                    if latest_previous_transaction and latest_previous_transaction.new_balance is not None:
                        old_balance = latest_previous_transaction.new_balance
                    else:
                        # No previous transaction, try to get the first transaction after this one
                        earliest_next_transaction = (
                            Transactions.objects.filter(
                                shop_id=transaction.shop_id,
                                created_at__gt=transaction.created_at,
                            )
                            .order_by('created_at')
                            .first()
                        )
                        
                        if earliest_next_transaction and earliest_next_transaction.old_balance is not None:
                            # Calculate old_balance based on next transaction's old_balance
                            # Our new_balance will cascade to become next transaction's old_balance
                            # For DEBIT: old_balance - amount = next.old_balance => old_balance = next.old_balance + amount
                            # For CREDIT: old_balance + amount = next.old_balance => old_balance = next.old_balance - amount
                            # if transaction.tr_type == 'DEBIT':
                            #     old_balance = earliest_next_transaction.old_balance + transaction.amount
                            # else:
                            #     old_balance = earliest_next_transaction.old_balance - transaction.amount
                            old_balance = earliest_next_transaction.old_balance
                        else:
                            # No previous or next transaction, use shop's current balance
                            old_balance = shop.balance
                    
                    # Calculate new balance
                    if transaction.tr_type == 'DEBIT':
                        new_balance = old_balance - transaction.amount
                        # Check if DEBIT transaction amount exceeds available balance
                        if transaction.amount > old_balance:
                            form.add_error(None, f'Insufficient balance. Available balance: {old_balance}')
                            context = {
                                'nav_title':'Add Entries',
                                'form': form,
                                'transfer_form': TransferForm(),
                                'loan_form': LoanForm(),
                            }
                            return render(request, 'entries/add_entries.html', context)
                    else:
                        new_balance = old_balance + transaction.amount
                    
                    # Store old and new balance
                    transaction.old_balance = old_balance
                    transaction.new_balance = new_balance
                    
                    # Update shop balance (calculate the difference from previous state)
                    if transaction.tr_type == 'DEBIT':
                        shop.balance = shop.balance - transaction.amount
                    else:
                        shop.balance = shop.balance + transaction.amount
                    
                    # Save transaction first
                    transaction.save()
                    
                    # Update all subsequent transactions
                    transaction_helper.update_latest_transactions(request, transaction, new_balance)
                    
                    # Save shop balance
                    shop.save()
                    
                # Refresh to get shop name
                transaction.refresh_from_db()
                logger.info(f"Transaction created by {request.user.username}: {transaction.tr_type} {transaction.amount} on {transaction.shop.name}")
                messages.success(request, 'Transaction added successfully!')
            except Exception as e:
                logger.error(f"Error creating transaction by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while creating transaction.')
                context = {
                    'nav_title':'Add Entries',
                    'form': form,
                    'transfer_form': TransferForm(),
                    'loan_form': LoanForm(),
                }
                return render(request, 'entries/add_entries.html', context)
            return redirect('entries:add_entries')
    
    context = {
        'nav_title':'Add Entries',
        'form': form,
        'transfer_form': transfer_form,
        'loan_form': loan_form,
    }
    
    return render(request, 'entries/add_entries.html', context)

@login_required
def transfer(request):
    if request.method == 'POST':
        form = TransferForm(request.POST)
        if form.is_valid():
            from_ledger_obj = form.cleaned_data['from_ledger']
            to_ledger_obj = form.cleaned_data['to_ledger']
            amount = form.cleaned_data['amount']
            name = form.cleaned_data['name']
            remarks = form.cleaned_data['remarks'] or f"Transfer to {to_ledger_obj.name} from {from_ledger_obj.name}"
            
            try:
                with db_transaction.atomic():
                    # Get ledgers and lock the shop rows to prevent race conditions
                    from_ledger = Ledger.objects.get(pk=from_ledger_obj.pk)
                    to_ledger = Ledger.objects.get(pk=to_ledger_obj.pk)
                    
                    # Lock unique shops
                    shop_ids = list(set(filter(None, [from_ledger.shop_id, to_ledger.shop_id])))
                    shops = {s.pk: s for s in Shop.objects.select_for_update().filter(pk__in=shop_ids)}
                    from_shop = shops[from_ledger.shop_id]
                    to_shop = shops[to_ledger.shop_id]
                    
                    # Check if from_shop has sufficient balance
                    if amount > from_shop.balance:
                        messages.error(request, f'Insufficient balance in {from_shop.name}. Current balance: {from_shop.balance}')
                        return redirect('entries:add_entries')
                    
                    # Create DEBIT transaction for from_ledger
                    old_balance_from = from_shop.balance
                    new_balance_from = old_balance_from - amount
                    
                    debit_transaction = Transactions.objects.create(
                        amount=amount,
                        name=name,
                        shop=from_shop,
                        tr_type='DEBIT',
                        remarks=remarks,
                        old_balance=old_balance_from,
                        new_balance=new_balance_from,
                        created_by=request.user if request.user.is_authenticated else None,
                        updated_by=request.user if request.user.is_authenticated else None,
                    )
                    
                    # Update from_shop balance
                    from_shop.balance = new_balance_from
                    from_shop.save()
                    
                    # Refresh to_shop if same as from_shop
                    if from_shop.pk == to_shop.pk:
                        to_shop = from_shop
                    
                    # Create CREDIT transaction for to_ledger
                    old_balance_to = to_shop.balance
                    new_balance_to = old_balance_to + amount
                    
                    credit_transaction = Transactions.objects.create(
                        amount=amount,
                        name=name,
                        shop=to_shop,
                        tr_type='CREDIT',
                        remarks=remarks,
                        old_balance=old_balance_to,
                        new_balance=new_balance_to,
                        created_by=request.user if request.user.is_authenticated else None,
                        updated_by=request.user if request.user.is_authenticated else None,
                    )
                    
                    # Update to_shop balance
                    to_shop.balance = new_balance_to
                    to_shop.save()
                    
                    logger.info(f"Transfer completed by {request.user.username}: {amount} from {from_ledger.name} to {to_ledger.name}")
                    messages.success(request, f'Successfully transferred {amount} from {from_ledger.name} to {to_ledger.name}')
            except Exception as e:
                logger.error(f"Error during transfer by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while processing the transfer.')
        else:
            # Form has validation errors, show them to the user
            messages.error(request, 'Please correct the errors in the transfer form.')
    
    return redirect('entries:add_entries')

@login_required
def transactions(request):
    # Get filter parameters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    shop_filter = request.GET.get('shop')
    type_filter = request.GET.get('type')
    search_query = request.GET.get('search', '')
    name_search_query = request.GET.get('name_search', '')
    
    # Base queryset - order by created date descending
    transactions_list = Transactions.objects.select_related('shop', 'created_by', 'updated_by').order_by('-created_at','-updated_at')
    
    # Apply filters
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            transactions_list = transactions_list.filter(created_at__date__gte=from_date_obj)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            transactions_list = transactions_list.filter(created_at__date__lte=to_date_obj)
        except ValueError:
            pass
    
    if shop_filter:
        transactions_list = transactions_list.filter(shop_id=shop_filter)
    
    if type_filter and type_filter in ['DEBIT', 'CREDIT']:
        transactions_list = transactions_list.filter(tr_type=type_filter)
    
    if name_search_query:
        transactions_list = transactions_list.filter(name__icontains=name_search_query)
    
    if search_query:
        transactions_list = transactions_list.filter(remarks__icontains=search_query)
    
    # Pagination
    paginator = Paginator(transactions_list, 25)  # Show 25 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate totals for all filtered transactions (not just current page)
    totals = transactions_list.aggregate(
        debit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='DEBIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        credit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='CREDIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    
    # Get all shops for filter dropdown
    all_shops = Shop.objects.all().order_by('name')
    
    context = {
        'nav_title': 'Other Transactions',
        'page_obj': page_obj,
        'all_transactions': transactions_list,  # All filtered transactions for printing
        'all_shops': all_shops,
        'from_date': from_date,
        'to_date': to_date,
        'shop_filter': shop_filter,
        'type_filter': type_filter,
        'search_query': search_query,
        'name_search_query': name_search_query,
        'debit_total': totals['debit_total'],
        'credit_total': totals['credit_total'],
        'is_admin_user': is_admin(request.user),
    }
    return render(request, 'entries/transactions.html', context)

def _get_filtered_transactions(request):
    """Helper function to get filtered transactions for exports"""
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    shop_filter = request.GET.get('shop')
    type_filter = request.GET.get('type')
    search_query = request.GET.get('search', '')
    name_search_query = request.GET.get('name_search', '')
    
    # Base queryset - order by created date descending
    transactions_list = Transactions.objects.select_related('shop', 'created_by', 'updated_by').order_by('-created_at','-updated_at')
    
    # Apply filters
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            transactions_list = transactions_list.filter(created_at__date__gte=from_date_obj)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            transactions_list = transactions_list.filter(created_at__date__lte=to_date_obj)
        except ValueError:
            pass
    
    if shop_filter:
        transactions_list = transactions_list.filter(shop_id=shop_filter)
    
    if type_filter and type_filter in ['DEBIT', 'CREDIT']:
        transactions_list = transactions_list.filter(tr_type=type_filter)
    
    if name_search_query:
        transactions_list = transactions_list.filter(name__icontains=name_search_query)
    
    if search_query:
        transactions_list = transactions_list.filter(remarks__icontains=search_query)
    
    return transactions_list

@login_required
def export_transactions_csv(request):
    transactions = _get_filtered_transactions(request)
    
    # Get filter parameters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    shop_filter = request.GET.get('shop')
    type_filter = request.GET.get('type')
    search_query = request.GET.get('search')
    name_search_query = request.GET.get('name_search')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_{timezone.localdate()}.csv"'
    
    writer = csv.writer(response)
    
    # Add filter information
    writer.writerow(['Transactions Export'])
    writer.writerow(['Export Date:', timezone.localdate()])
    writer.writerow(['Exported By:', f'{request.user.first_name} {request.user.last_name}'])
    writer.writerow([])
    
    # Add applied filters
    writer.writerow(['Applied Filters:'])
    if from_date:
        writer.writerow(['From Date:', from_date])
    if to_date:
        writer.writerow(['To Date:', to_date])
    if shop_filter:
        try:
            shop = Shop.objects.get(pk=shop_filter)
            writer.writerow(['Shop:', shop.name])
        except Shop.DoesNotExist:
            pass
    if type_filter:
        writer.writerow(['Type:', type_filter])
    if name_search_query:
        writer.writerow(['Name Search:', name_search_query])
    if search_query:
        writer.writerow(['Remarks Search:', search_query])
    if not any([from_date, to_date, shop_filter, type_filter, search_query, name_search_query]):
        writer.writerow(['No filters applied - showing all transactions'])
    writer.writerow([])
    
    # Transaction headers
    writer.writerow(['Date', 'Time', 'Shop', 'Name', 'Type', 'Amount', 'Remarks', 'Created By', 'Updated By'])
    
    for transaction in transactions:
        writer.writerow([
            transaction.created_at.strftime('%Y-%m-%d'),
            transaction.created_at.strftime('%H:%M:%S'),
            transaction.shop.name,
            transaction.name or '-',
            transaction.tr_type,
            transaction.amount,
            transaction.remarks or '-',
            transaction.created_by.username,
            transaction.updated_by.username,
        ])
    
    # Add totals
    totals = transactions.aggregate(
        debit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='DEBIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        credit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='CREDIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    
    writer.writerow([])
    writer.writerow(['', '', '', 'TOTAL:', 'DEBIT', totals['debit_total'], '', '', ''])
    writer.writerow(['', '', '', '', 'CREDIT', totals['credit_total'], '', '', ''])
    
    logger.info(f"Transactions CSV export by {request.user.username}")
    
    return response

@login_required
def export_transactions_excel(request):
    transactions = _get_filtered_transactions(request)
    
    # Get filter parameters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    shop_filter = request.GET.get('shop')
    type_filter = request.GET.get('type')
    search_query = request.GET.get('search')
    name_search_query = request.GET.get('name_search')
    
    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transactions"
    
    # Header styling
    header_fill = PatternFill(start_color="4A7766", end_color="4A7766", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    # Title
    ws.merge_cells('A1:I1')
    title_cell = ws['A1']
    title_cell.value = f"Transactions Export - {timezone.localdate()}"
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = Alignment(horizontal="center")
    
    # Add exported by info
    ws.merge_cells('A2:I2')
    export_cell = ws['A2']
    export_cell.value = f"Exported by: {request.user.first_name} {request.user.last_name}"
    export_cell.alignment = Alignment(horizontal="right")
    export_cell.font = Font(italic=True, size=9)
    
    current_row = 4
    
    # Add filter information
    if any([from_date, to_date, shop_filter, type_filter, search_query, name_search_query]):
        ws.merge_cells(f'A{current_row}:I{current_row}')
        filter_title = ws.cell(row=current_row, column=1)
        filter_title.value = "Applied Filters:"
        filter_title.font = Font(bold=True, size=11)
        current_row += 1
        
        if from_date:
            ws.cell(row=current_row, column=1, value="From Date:")
            ws.cell(row=current_row, column=2, value=from_date)
            current_row += 1
        
        if to_date:
            ws.cell(row=current_row, column=1, value="To Date:")
            ws.cell(row=current_row, column=2, value=to_date)
            current_row += 1
        
        if shop_filter:
            try:
                shop_obj = Shop.objects.get(pk=shop_filter)
                ws.cell(row=current_row, column=1, value="Shop:")
                ws.cell(row=current_row, column=2, value=shop_obj.name)
                current_row += 1
            except Shop.DoesNotExist:
                pass
        
        if type_filter:
            ws.cell(row=current_row, column=1, value="Type:")
            type_cell = ws.cell(row=current_row, column=2, value=type_filter)
            if type_filter == 'DEBIT':
                type_cell.font = Font(color="FF0000", bold=True)
            else:
                type_cell.font = Font(color="008000", bold=True)
            current_row += 1
        
        if name_search_query:
            ws.cell(row=current_row, column=1, value="Name Search:")
            ws.cell(row=current_row, column=2, value=name_search_query)
            current_row += 1
        
        if search_query:
            ws.cell(row=current_row, column=1, value="Remarks Search:")
            ws.cell(row=current_row, column=2, value=search_query)
            current_row += 1
        
        current_row += 1  # Add space after filters
    else:
        ws.merge_cells(f'A{current_row}:I{current_row}')
        no_filter_cell = ws.cell(row=current_row, column=1)
        no_filter_cell.value = "No filters applied - showing all transactions"
        no_filter_cell.font = Font(italic=True, size=9)
        current_row += 2
    
    # Headers
    headers = ['Date', 'Time', 'Shop', 'Name', 'Type', 'Amount', 'Remarks', 'Created By', 'Updated By']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=current_row, column=col)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
    current_row += 1
    
    # Transaction Data
    for transaction in transactions:
        ws.cell(row=current_row, column=1, value=transaction.created_at.strftime('%Y-%m-%d'))
        ws.cell(row=current_row, column=2, value=transaction.created_at.strftime('%H:%M:%S'))
        ws.cell(row=current_row, column=3, value=transaction.shop.name)
        ws.cell(row=current_row, column=4, value=transaction.name or '-')
        
        type_cell = ws.cell(row=current_row, column=5, value=transaction.tr_type)
        if transaction.tr_type == 'DEBIT':
            type_cell.font = Font(color="FF0000", bold=True)
            amount_cell = ws.cell(row=current_row, column=6, value=float(transaction.amount))
            amount_cell.font = Font(color="FF0000")
        else:
            type_cell.font = Font(color="008000", bold=True)
            amount_cell = ws.cell(row=current_row, column=6, value=float(transaction.amount))
            amount_cell.font = Font(color="008000")
        
        ws.cell(row=current_row, column=7, value=transaction.remarks or '-')
        ws.cell(row=current_row, column=8, value=transaction.created_by.username)
        ws.cell(row=current_row, column=9, value=transaction.updated_by.username)
        current_row += 1
    
    # Totals
    totals = transactions.aggregate(
        debit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='DEBIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        credit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='CREDIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    
    total_row = current_row + 1
    total_cell = ws.cell(row=total_row, column=4, value='TOTAL:')
    total_cell.font = Font(bold=True)
    total_cell.alignment = Alignment(horizontal="right")
    
    debit_label = ws.cell(row=total_row, column=5, value='DEBIT')
    debit_label.font = Font(bold=True, color="FF0000")
    
    debit_total_cell = ws.cell(row=total_row, column=6, value=float(totals['debit_total']))
    debit_total_cell.font = Font(bold=True, color="FF0000")
    
    credit_label = ws.cell(row=total_row + 1, column=5, value='CREDIT')
    credit_label.font = Font(bold=True, color="008000")
    
    credit_total_cell = ws.cell(row=total_row + 1, column=6, value=float(totals['credit_total']))
    credit_total_cell.font = Font(bold=True, color="008000")
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 10
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 30
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 15
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="transactions_{timezone.localdate()}.xlsx"'
    wb.save(response)
    
    logger.info(f"Transactions Excel export by {request.user.username}")
    
    return response

@login_required
@admin_or_staff_required
def edit_transaction(request, pk):
    transaction = get_object_or_404(Transactions, pk=pk)
    old_shop_id = transaction.shop_id
    old_trans_old_bal = transaction.old_balance
    old_trans_new_bal = transaction.new_balance
    old_created_at = transaction.created_at
    old_amount = transaction.amount
    old_type = transaction.tr_type
    old_shop = transaction.shop
    
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            updated_transaction = form.save(commit=False)
            if request.user.is_authenticated:
                updated_transaction.updated_by = request.user
            
            # Apply chosen date+time to created_at BEFORE balance calculations
            chosen_date = form.cleaned_data.get('date')
            if chosen_date:
                chosen_time = form.cleaned_data.get('time') or timezone.localtime(timezone.now()).time()
                updated_transaction.created_at = timezone.make_aware(
                    datetime.combine(chosen_date, chosen_time)
                )
            
            try:
                with db_transaction.atomic():
                    # Lock shop(s) to prevent race conditions
                    if old_shop_id == updated_transaction.shop_id:
                        
                        # Same shop - lock it
                        shop = Shop.objects.select_for_update().get(pk=updated_transaction.shop_id)
                        
                        # Reverse old transaction effect
                        if old_type == 'DEBIT':
                            shop.balance += old_amount
                        else:
                            shop.balance -= old_amount
                        
                        # Get the previous transaction to chain balances
                        latest_previous_transaction = (
                            Transactions.objects.filter(
                                shop_id=updated_transaction.shop_id,
                                created_at__lt=updated_transaction.created_at,
                            )
                            .exclude(pk=transaction.pk)
                            .order_by('-created_at')
                            .first()
                        )
                        
                        # Get old_balance from previous transaction's new_balance
                        if latest_previous_transaction and latest_previous_transaction.new_balance is not None:
                            old_balance = latest_previous_transaction.new_balance
                        else:
                            # No previous transaction, try to get the first transaction after this one
                            earliest_next_transaction = (
                                Transactions.objects.filter(
                                    shop_id=updated_transaction.shop_id,
                                    created_at__gt=updated_transaction.created_at,
                                )
                                .exclude(pk=transaction.pk)
                                .order_by('created_at')
                                .first()
                            )
                            
                            if earliest_next_transaction.created_at >= old_created_at:
                                old_balance = old_trans_old_bal
                            else:
                                # No previous or next transaction, use shop's balance (after reversing old effect)
                                old_balance = earliest_next_transaction.old_balance
                        
                        # Calculate new balance
                        if updated_transaction.tr_type == 'DEBIT':
                            # Check if DEBIT transaction amount exceeds available balance
                            if updated_transaction.amount > old_balance:
                                # Rollback will happen automatically due to transaction.atomic
                                form.add_error(None, f'Insufficient balance. Available balance: {old_balance}')
                                context = {
                                    'nav_title': 'Other Transactions',
                                    'form': form,
                                    'transaction': transaction,
                                }
                                return render(request, 'entries/edit-transaction.html', context)
                            new_balance = old_balance - updated_transaction.amount
                            shop.balance = shop.balance - updated_transaction.amount
                        else:
                            new_balance = old_balance + updated_transaction.amount
                            shop.balance = shop.balance + updated_transaction.amount
                        
                        # Update subsequent transactions
                        transaction_helper.update_latest_transactions(request, updated_transaction, new_balance)
                        shop.save()
                    else:
                        # Different shops - lock both
                        shop_ids = list(set([old_shop_id, updated_transaction.shop_id]))
                        shops = {s.pk: s for s in Shop.objects.select_for_update().filter(pk__in=shop_ids)}
                        old_shop_obj = shops[old_shop_id]
                        new_shop = shops[updated_transaction.shop_id]
                        
                        # Reverse old transaction effect on old shop
                        if old_type == 'DEBIT':
                            old_shop_obj.balance += old_amount
                            old_trans_new_bal = old_trans_new_bal + old_amount
                        else:
                            old_shop_obj.balance -= old_amount
                            old_trans_new_bal = old_trans_new_bal - old_amount
                        transaction_helper.update_latest_transactions(request,updated_transaction,old_trans_new_bal,old_shop_id)
                        latest_previous_transaction = (
                            Transactions.objects.filter(
                                shop_id=updated_transaction.shop_id,
                                created_at__lt=updated_transaction.created_at,
                            )
                            .exclude(pk=transaction.pk)
                            .order_by('-created_at')
                            .first()
                        )
                        
                        # Get old_balance from previous transaction's new_balance
                        if latest_previous_transaction and latest_previous_transaction.new_balance is not None:
                            old_balance = latest_previous_transaction.new_balance
                        else:
                            # No previous transaction, try to get the first transaction after this one
                            earliest_next_transaction = (
                                Transactions.objects.filter(
                                    shop_id=updated_transaction.shop_id,
                                    created_at__gt=updated_transaction.created_at,
                                )
                                .exclude(pk=transaction.pk)
                                .order_by('created_at')
                                .first()
                            )
                            
                            old_balance = earliest_next_transaction.old_balance
                        
                        # Check if DEBIT transaction amount exceeds available balance
                        if updated_transaction.tr_type == 'DEBIT':
                            if updated_transaction.amount > old_balance:
                                form.add_error(None, f'Insufficient balance in {new_shop.name}. Available balance: {old_balance}')
                                context = {
                                    'nav_title': 'Other Transactions',
                                    'form': form,
                                    'transaction': transaction,
                                }
                                return render(request, 'entries/edit-transaction.html', context)
                        
                        # Apply new transaction effect on new shop
                        if updated_transaction.tr_type == 'DEBIT':
                            new_balance = old_balance - updated_transaction.amount
                            new_shop.balance = new_shop.balance - updated_transaction.amount
                        else:
                            new_balance = old_balance + updated_transaction.amount
                            new_shop.balance = new_shop.balance + updated_transaction.amount
                        old_shop_obj.save()
                        if old_shop_obj.pk != new_shop.pk:
                            new_shop.save()
                    
                    # Update old and new balance fields
                    updated_transaction.old_balance = old_balance
                    updated_transaction.new_balance = new_balance
                    updated_transaction.save()
                    transaction_helper.update_latest_transactions(request,updated_transaction,new_balance)
                
                # Build change summary
                changes = []
                if old_amount != updated_transaction.amount:
                    changes.append(f"amount: {old_amount} -> {updated_transaction.amount}")
                if old_type != updated_transaction.tr_type:
                    changes.append(f"type: {old_type} -> {updated_transaction.tr_type}")
                if old_shop_id != updated_transaction.shop_id:
                    changes.append(f"shop: {old_shop.name} -> {updated_transaction.shop.name}")
                change_summary = ', '.join(changes) if changes else 'no changes'
                logger.info(f"Transaction edited by {request.user.username}: ID {pk}, changes: {change_summary}")
            except Exception as e:
                logger.error(f"Error editing transaction {pk} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while editing transaction.')
                context = {
                    'nav_title': 'Other Transactions',
                    'form': form,
                    'transaction': transaction,
                }
                return render(request, 'entries/edit-transaction.html', context)
            
            return redirect('entries:transactions')
    else:
        form = TransactionForm(
            instance=transaction,
            initial={'date': timezone.localtime(transaction.created_at).date(), 'time': timezone.localtime(transaction.created_at).time().replace(second=0, microsecond=0)},
        )
    
    context = {
        'nav_title': 'Other Transactions',
        'form': form,
        'transaction': transaction,
    }
    return render(request, 'entries/edit-transaction.html', context)

@login_required
@admin_required
def delete_transaction(request, pk):
    transaction = get_object_or_404(Transactions, pk=pk)
    
    if request.method == 'POST':
        transaction_id = transaction.id
        transaction_amount = transaction.amount
        transaction_type = transaction.tr_type
        shop_name = transaction.shop.name
        
        try:
            with db_transaction.atomic():
                # Lock the shop to prevent race conditions
                shop = Shop.objects.select_for_update().get(pk=transaction.shop_id)
                
                # Reverse transaction effect on shop balance
                if transaction.tr_type == 'DEBIT':
                    shop.balance += transaction.amount
                else:
                    shop.balance -= transaction.amount
                
                shop.save()
                transaction_helper.update_latest_transactions(request,transaction,transaction.old_balance)
                transaction.delete()
            
            logger.warning(f"Transaction deleted by {request.user.username}: ID {transaction_id}, {transaction_type} {transaction_amount} on {shop_name}")
        except Exception as e:
            logger.error(f"Error deleting transaction {transaction_id} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting transaction.')
            return redirect('entries:transactions')
        
        return redirect('entries:transactions')
    
    context = {
        'nav_title': 'Other Transactions',
        'transaction': transaction,
    }
    return render(request, 'entries/delete-transaction.html', context)

@login_required
@admin_required
def add_ledger(request):
    if request.method == 'POST':
        form = LedgerForm(request.POST)
        if form.is_valid():
            try:
                with db_transaction.atomic():
                    # Create ledger
                    ledger = form.save(commit=False)
                    ledger.save()
                    logger.info(f"Ledger created by {request.user.username}: name={ledger.name}, balance=0")
                    
                return redirect('entries:home')
            except Exception as e:
                logger.error(f"Error creating ledger by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while creating ledger.')
    else:
        form = LedgerForm()
    
    context = {
        'nav_title': 'Home',
        'form': form,
    }
    return render(request, 'entries/add-ledger.html', context)


@login_required
def report(request):
    # Get filter parameters
    report_date = request.GET.get('date')
    shop_id = request.GET.get('shop')
    
    # Use today's date if no date specified
    if not report_date:
        report_date = timezone.localdate()
    else:
        # Convert string date to date object for template rendering
        try:
            report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
        except ValueError:
            report_date = timezone.localdate()
    
    # Log report generation
    filter_info = f"shop_id={shop_id}" if shop_id else "all shops"
    logger.info(f"Report generated by {request.user.username}: date={report_date}, filter={filter_info}")
    
    # Base queryset - filter by date
    transactions = Transactions.objects.filter(
        created_at__date=report_date
    ).select_related('shop', 'created_by', 'updated_by')
    
    # Apply shop filter if specified
    if shop_id:
        transactions = transactions.filter(shop_id=shop_id)
    
    transactions = transactions.order_by('created_at')
    
    # Calculate totals for the day
    totals = transactions.aggregate(
        debit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='DEBIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        credit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='CREDIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    
    # Calculate shop balances (opening and closing)
    shop_summaries = []
    shops_to_process = Shop.objects.filter(id=shop_id) if shop_id else Shop.objects.all()
    
    for shop in shops_to_process.order_by('name'):
        # Get first transaction of the day for this shop to fetch opening balance
        first_transaction = Transactions.objects.filter(
            shop=shop,
            created_at__date=report_date
        ).order_by('created_at').first()
        
        if first_transaction and first_transaction.old_balance is not None:
            opening_balance = first_transaction.old_balance
        else:
            # No transactions on this date, get last transaction before this date
            last_transaction = Transactions.objects.filter(
                shop=shop,
                created_at__date__lt=report_date
            ).order_by('-created_at').first()
            
            if last_transaction and last_transaction.new_balance is not None:
                opening_balance = last_transaction.new_balance
            else:
                # No transactions before this date, opening balance = 0
                opening_balance = '0.00'
        
        # Get transactions for this shop on this date for totals
        shop_day_transactions = Transactions.objects.filter(
            shop=shop,
            created_at__date=report_date
        ).aggregate(
            debit_total=Coalesce(
                Sum(
                    Case(
                        When(tr_type='DEBIT', then=F('amount')),
                        default=Value(0),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            credit_total=Coalesce(
                Sum(
                    Case(
                        When(tr_type='CREDIT', then=F('amount')),
                        default=Value(0),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        
        debit_total = shop_day_transactions['debit_total']
        credit_total = shop_day_transactions['credit_total']
        
        if first_transaction:
            # Closing balance is current shop balance
            closing_balance = shop.balance
        else:
            last_transaction = Transactions.objects.filter(
                shop=shop,
                created_at__date__lt=report_date
            ).order_by('-created_at').first()
            
            if last_transaction and last_transaction.new_balance is not None:
                closing_balance = last_transaction.new_balance
            else:
                # No transactions before this date, opening balance = 0
                closing_balance = '0.00'
        
        
        shop_summaries.append({
            'shop': shop,
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
            'debit_total': debit_total,
            'credit_total': credit_total,
        })
    
    all_shops = Shop.objects.all().order_by('name')
    
    # Get loan and release summaries for the report date
    loan_entries = Loan.objects.filter(
        type='LOAN',
        created_at__date=report_date
    ).values('pawn_no', 'principal', 'interest')
    
    release_entries = Loan.objects.filter(
        type='RELEASE',
        created_at__date=report_date
    ).values('pawn_no', 'principal', 'interest')
    
    # Calculate totals for loans
    loan_totals = Loan.objects.filter(
        type='LOAN',
        created_at__date=report_date
    ).aggregate(
        total_principal=Coalesce(Sum('principal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_interest=Coalesce(Sum('interest'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
    )
    
    # Calculate totals for releases
    release_totals = Loan.objects.filter(
        type='RELEASE',
        created_at__date=report_date
    ).aggregate(
        total_principal=Coalesce(Sum('principal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_interest=Coalesce(Sum('interest'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
    )
    
    # Fetch denominations for the current user on the report date, grouped by time period
    TIME_PERIOD_ORDER = {'MORNING': 1, 'AFTERNOON': 2, 'EVENING': 3, 'NIGHT': 4}
    denom_filter = {'created_by': request.user, 'created_at__date': report_date}
    if shop_id:
        denom_filter['shop_id'] = shop_id
    denomination_entries_qs = (
        Denomination.objects
        .filter(**denom_filter)
        .values('time_period', 'denomination', 'count', 'amount', 'shop__name')
        .order_by('time_period', 'denomination')
    )
    # Group denominations by time_period
    denomination_by_period = {}
    for entry in denomination_entries_qs:
        period = entry['time_period']
        if period not in denomination_by_period:
            denomination_by_period[period] = {
                'rows': [],
                'total': Decimal('0.00'),
                'shop_name': entry.get('shop__name') or '',
            }
        denomination_by_period[period]['rows'].append(entry)
        denomination_by_period[period]['total'] += entry['amount']
    # Sort periods by natural order
    denomination_periods = sorted(
        denomination_by_period.items(),
        key=lambda x: TIME_PERIOD_ORDER.get(x[0], 99)
    )

    context = {
        'nav_title': 'Report',
        'transactions': transactions,
        'all_shops': all_shops,
        'report_date': report_date,
        'selected_shop': shop_id,
        'debit_total': totals['debit_total'],
        'credit_total': totals['credit_total'],
        'shop_summaries': shop_summaries,
        'loan_entries': loan_entries,
        'release_entries': release_entries,
        'loan_totals': loan_totals,
        'release_totals': release_totals,
        'denomination_periods': denomination_periods,
    }
    return render(request, 'entries/report.html', context)


@login_required
def export_report_csv(request):
    report_date = request.GET.get('date')
    shop_id = request.GET.get('shop')
    
    if not report_date:
        report_date = timezone.localdate()
    else:
        # Convert string date to date object
        try:
            report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
        except ValueError:
            report_date = timezone.localdate()
    
    # Get transactions
    transactions = Transactions.objects.filter(
        created_at__date=report_date
    ).select_related('shop', 'created_by', 'updated_by')
    
    if shop_id:
        transactions = transactions.filter(shop_id=shop_id)
    
    transactions = transactions.order_by('created_at')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transaction_report_{report_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'Shop', 'Name', 'Remarks', 'DEBIT', 'CREDIT', 'Created By', 'Updated By'])
    
    for transaction in transactions:
        debit = transaction.amount if transaction.tr_type == 'DEBIT' else ''
        credit = transaction.amount if transaction.tr_type == 'CREDIT' else ''
        writer.writerow([
            transaction.created_at.strftime('%Y-%m-%d'),
            transaction.created_at.strftime('%H:%M:%S'),
            transaction.shop.name,
            transaction.name or '-',
            transaction.remarks or '-',
            debit,
            credit,
            transaction.created_by.username,
            transaction.updated_by.username,
        ])
    
    # Add totals
    totals = transactions.aggregate(
        debit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='DEBIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        credit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='CREDIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    
    writer.writerow([])
    writer.writerow(['', '', '', 'TOTAL:', '', totals['debit_total'], totals['credit_total'], '', ''])
    
    filter_info = f"shop_id={shop_id}" if shop_id else "all shops"
    logger.info(f"CSV export by {request.user.username}: date={report_date}, filter={filter_info}")
    
    return response


@login_required
def export_report_excel(request):
    report_date = request.GET.get('date')
    shop_id = request.GET.get('shop')
    
    if not report_date:
        report_date = timezone.localdate()
    else:
        # Convert string date to date object
        try:
            report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
        except ValueError:
            report_date = timezone.localdate()
    
    # Get transactions
    transactions = Transactions.objects.filter(
        created_at__date=report_date
    ).select_related('shop', 'created_by', 'updated_by')
    
    if shop_id:
        transactions = transactions.filter(shop_id=shop_id)
    
    transactions = transactions.order_by('created_at')
    
    # Calculate shop balances
    shop_summaries = []
    shops_to_process = Shop.objects.filter(id=shop_id) if shop_id else Shop.objects.all()
    
    for shop in shops_to_process.order_by('name'):
        # Get first transaction of the day for this shop to fetch opening balance
        first_transaction = Transactions.objects.filter(
            shop=shop,
            created_at__date=report_date
        ).order_by('created_at').first()
        
        if first_transaction and first_transaction.old_balance is not None:
            opening_balance = first_transaction.old_balance
        else:
            # No transactions on this date, get last transaction before this date
            last_transaction = Transactions.objects.filter(
                shop=shop,
                created_at__date__lt=report_date
            ).order_by('-created_at').first()
            
            if last_transaction and last_transaction.new_balance is not None:
                opening_balance = last_transaction.new_balance
            else:
                # No transactions before this date, opening balance = 0
                opening_balance = '0.00'
        
        shop_day_transactions = Transactions.objects.filter(
            shop=shop,
            created_at__date=report_date
        ).aggregate(
            debit_total=Coalesce(
                Sum(
                    Case(
                        When(tr_type='DEBIT', then=F('amount')),
                        default=Value(0),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            credit_total=Coalesce(
                Sum(
                    Case(
                        When(tr_type='CREDIT', then=F('amount')),
                        default=Value(0),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        
        debit_total = shop_day_transactions['debit_total']
        credit_total = shop_day_transactions['credit_total']
        
        # Closing balance is current shop balance
        closing_balance = shop.balance
        
        shop_summaries.append({
            'shop': shop,
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
            'debit_total': debit_total,
            'credit_total': credit_total,
        })
    
    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transaction Report"
    
    # Header styling
    header_fill = PatternFill(start_color="4A7766", end_color="4A7766", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    # Title
    ws.merge_cells('A1:I1')
    title_cell = ws['A1']
    title_cell.value = f"Transaction Report - {report_date}"
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = Alignment(horizontal="center")
    
    # Add exported by info
    ws.merge_cells('A2:I2')
    export_cell = ws['A2']
    export_cell.value = f"Exported by: {request.user.first_name} {request.user.last_name}"
    export_cell.alignment = Alignment(horizontal="right")
    export_cell.font = Font(italic=True, size=9)
    
    current_row = 4
    
    # Add Shop Balances Section
    if shop_summaries:
        ws.merge_cells(f'A{current_row}:H{current_row}')
        balance_title = ws.cell(row=current_row, column=1)
        balance_title.value = "Shop Balances Summary"
        balance_title.font = Font(bold=True, size=12)
        balance_title.alignment = Alignment(horizontal="center")
        current_row += 1
        
        # Shop balance headers
        balance_headers = ['Shop', 'Opening Balance', 'Closing Balance', "Day's Debit", "Day's Credit"]
        for col, header in enumerate(balance_headers, start=1):
            cell = ws.cell(row=current_row, column=col)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
        current_row += 1
        
        # Shop balance data
        for summary in shop_summaries:
            ws.cell(row=current_row, column=1, value=summary['shop'].name)
            ws.cell(row=current_row, column=2, value=float(summary['opening_balance']))
            ws.cell(row=current_row, column=3, value=float(summary['closing_balance']))
            
            debit_cell = ws.cell(row=current_row, column=4, value=float(summary['debit_total']))
            debit_cell.font = Font(color="FF0000")
            
            credit_cell = ws.cell(row=current_row, column=5, value=float(summary['credit_total']))
            credit_cell.font = Font(color="008000")
            current_row += 1
        
        current_row += 2  # Add space before transactions
    
    # Transactions section title
    ws.merge_cells(f'A{current_row}:I{current_row}')
    trans_title = ws.cell(row=current_row, column=1)
    trans_title.value = "Transactions"
    trans_title.font = Font(bold=True, size=12)
    trans_title.alignment = Alignment(horizontal="center")
    current_row += 1
    
    # Transaction Headers
    headers = ['Date', 'Time', 'Shop', 'Name', 'Remarks', 'DEBIT', 'CREDIT', 'Created By', 'Updated By']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=current_row, column=col)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
    current_row += 1
    
    # Transaction Data
    for transaction in transactions:
        ws.cell(row=current_row, column=1, value=transaction.created_at.strftime('%Y-%m-%d'))
        ws.cell(row=current_row, column=2, value=transaction.created_at.strftime('%H:%M:%S'))
        ws.cell(row=current_row, column=3, value=transaction.shop.name)
        ws.cell(row=current_row, column=4, value=transaction.name or '-')
        ws.cell(row=current_row, column=5, value=transaction.remarks or '-')
        
        if transaction.tr_type == 'DEBIT':
            debit_cell = ws.cell(row=current_row, column=6, value=float(transaction.amount))
            debit_cell.font = Font(color="FF0000")
            ws.cell(row=current_row, column=7, value='')
        else:
            ws.cell(row=current_row, column=6, value='')
            credit_cell = ws.cell(row=current_row, column=7, value=float(transaction.amount))
            credit_cell.font = Font(color="008000")
        
        ws.cell(row=current_row, column=8, value=transaction.created_by.username)
        ws.cell(row=current_row, column=9, value=transaction.updated_by.username)
        current_row += 1
    
    # Totals
    totals = transactions.aggregate(
        debit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='DEBIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        credit_total=Coalesce(
            Sum(
                Case(
                    When(tr_type='CREDIT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )
    
    total_row = current_row + 1
    total_cell = ws.cell(row=total_row, column=5, value='TOTAL:')
    total_cell.font = Font(bold=True)
    total_cell.alignment = Alignment(horizontal="right")
    
    debit_total_cell = ws.cell(row=total_row, column=6, value=float(totals['debit_total']))
    debit_total_cell.font = Font(bold=True, color="FF0000")
    
    credit_total_cell = ws.cell(row=total_row, column=7, value=float(totals['credit_total']))
    credit_total_cell.font = Font(bold=True, color="008000")
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 30
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 15
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="transaction_report_{report_date}.xlsx"'
    wb.save(response)
    
    filter_info = f"shop_id={shop_id}" if shop_id else "all shops"
    logger.info(f"Excel export by {request.user.username}: date={report_date}, filter={filter_info}")
    
    return response


@login_required
@admin_required
def ledger_info(request, pk):
    ledger = get_object_or_404(Ledger, pk=pk)
    
    # Get all loan transactions for this ledger
    loans_list = Loan.objects.filter(ledger=ledger).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(loans_list, 25)  # Show 25 loans per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate counts for loans and releases
    loan_count = Loan.objects.filter(ledger=ledger, type='LOAN').count()
    release_count = Loan.objects.filter(ledger=ledger, type='RELEASE').count()
    
    context = {
        'nav_title': 'Home',
        'ledger': ledger,
        'page_obj': page_obj,
        'loan_count': loan_count,
        'release_count': release_count,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'entries/ledger_info.html', context)


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
                return redirect('entries:ledger_info', pk=ledger.pk)
            except Exception as e:
                logger.error(f"Error editing ledger {pk} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while updating ledger.')
    else:
        form = LedgerForm(instance=ledger)
    
    context = {
        'nav_title': 'Home',
        'form': form,
        'ledger': ledger,
    }
    return render(request, 'entries/edit_ledger.html', context)


@login_required
@admin_required
def delete_ledger(request, pk):
    ledger = get_object_or_404(Ledger, pk=pk)
    
    if request.method == 'POST':
        # Check if ledger has transactions (via shop)
        if Transactions.objects.filter(shop=ledger.shop).exists():
            messages.error(request, f'Cannot delete ledger "{ledger.name}" because its shop has associated transactions.')
            logger.warning(f"Ledger deletion blocked by {request.user.username}: {ledger.name} shop has associated transactions")
            return redirect('entries:ledger_info', pk=ledger.pk)
        
        ledger_name = ledger.name
        try:
            ledger.delete()
            logger.warning(f"Ledger deleted by {request.user.username}: {ledger_name}")
            messages.success(request, f'Ledger "{ledger_name}" deleted successfully!')
        except Exception as e:
            logger.error(f"Error deleting ledger {ledger_name} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting ledger.')
            return redirect('entries:ledger_info', pk=ledger.pk)
        return redirect('entries:home')
    
    context = {
        'nav_title': 'Home',
        'ledger': ledger,
    }
    return render(request, 'entries/delete_ledger.html', context)

@login_required
def denomination(request):
    if request.method == 'POST':
        form = DenominationForm(request.POST)
        if form.is_valid():
            # Get form data
            time_period = form.cleaned_data.get('time_period')
            
            # Generate key: DDMMYYYY-XX-Username
            from datetime import datetime
            current_date = datetime.now().strftime('%d%m%Y')
            time_period_code = {
                'MORNING': '01',
                'AFTERNOON': '02',
                'EVENING': '03',
                'NIGHT': '04'
            }.get(time_period, '00')
            key = f"{current_date}-{time_period_code}-{request.user.username}"
            
            # Check if key already exists
            if Denomination.objects.filter(key=key).exists():
                messages.error(request, f'Denomination for {time_period.title()} on {datetime.now().strftime("%d-%m-%Y")} already exists!')
                return render(request, 'entries/denomination.html', {'form': form})
            
            shop = form.cleaned_data.get('shop')
            note_2000 = form.cleaned_data.get('note_2000') or 0
            note_500 = form.cleaned_data.get('note_500') or 0
            note_200 = form.cleaned_data.get('note_200') or 0
            note_100 = form.cleaned_data.get('note_100') or 0
            note_50 = form.cleaned_data.get('note_50') or 0
            note_20 = form.cleaned_data.get('note_20') or 0
            note_10 = form.cleaned_data.get('note_10') or 0
            coins = form.cleaned_data.get('coins') or Decimal('0.00')
            damage = form.cleaned_data.get('damage') or Decimal('0.00')
            
            try:
                # Calculate amounts and create denomination records
                denominations = [
                    ('2000', note_2000, note_2000 * 2000),
                    ('500', note_500, note_500 * 500),
                    ('200', note_200, note_200 * 200),
                    ('100', note_100, note_100 * 100),
                    ('50', note_50, note_50 * 50),
                    ('20', note_20, note_20 * 20),
                    ('10', note_10, note_10 * 10),
                    ('Coins', 1, coins),
                    ('Damage', 1, damage),
                ]
                
                for denom_name, count, amount in denominations:
                    if count > 0 or amount > 0:
                        Denomination.objects.create(
                            denomination=denom_name,
                            count=count,
                            amount=Decimal(str(amount)),
                            time_period=time_period,
                            key=key,
                            shop=shop,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                
                logger.info(f"Denomination added by {request.user.username}")
                messages.success(request, 'Denomination added successfully!')
                return redirect('entries:denominations')
            except Exception as e:
                logger.error(f"Error adding denomination by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while adding denomination.')
        else:
            messages.error(request, 'Please correct the errors in the form.')
    else:
        form = DenominationForm()
    
    context = {
        'nav_title': 'Denomination',
        'form': form,
    }
    return render(request, 'entries/denomination.html', context)


@login_required
def denominations(request):
    """List all denomination groups by key with totals."""
    is_super_admin = request.user.is_superuser
    is_admin_group_user = request.user.groups.filter(name='Admin').exists()
    is_staff_group_user = request.user.groups.filter(name='Staff').exists()

    denominations_qs = Denomination.objects.select_related('created_by')

    # Admin group users and super admins can view all; staff/others can view only their own
    if not is_admin_group_user and not is_super_admin:
        denominations_qs = denominations_qs.filter(created_by=request.user)

    denomination_groups = (
        denominations_qs.values(
            'key',
            'time_period',
            'created_by_id',
            'created_by__first_name',
            'created_by__last_name',
            'created_by__username',
            'shop__name',
        )
        .annotate(
            date=Min('created_at'),
            total=Coalesce(
                Sum('amount'),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-date')
    )

    context = {
        'nav_title': 'Denomination',
        'denomination_groups': denomination_groups,
        'is_super_admin': is_super_admin,
        'is_admin_group_user': is_admin_group_user,
        'is_staff_group_user': is_staff_group_user,
    }
    return render(request, 'entries/denominations.html', context)


@login_required
def delete_denomination(request, key):
    """Delete denomination group by key (admin group and super admin only)."""
    if request.method != 'POST':
        return redirect('entries:denominations')

    is_super_admin = request.user.is_superuser
    is_admin_group_user = request.user.groups.filter(name='Admin').exists()
    if not is_super_admin and not is_admin_group_user:
        raise PermissionDenied('You do not have permission to delete denominations.')

    denominations_qs = Denomination.objects.filter(key=key)
    if not denominations_qs.exists():
        messages.error(request, 'Denomination not found.')
        return redirect('entries:denominations')

    deleted_count = denominations_qs.count()
    denominations_qs.delete()

    logger.warning(
        f"Denomination group deleted by {request.user.username}: key={key}, records={deleted_count}"
    )
    messages.success(request, 'Denomination deleted successfully!')
    return redirect('entries:denominations')


@login_required
def get_users_for_denomination(request):
    """Get all users who have created denominations"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Admin can see all users, Staff can see only themselves
    if request.user.groups.filter(name='Admin').exists():
        users = User.objects.filter(created_denominations__isnull=False).distinct().values('id', 'username')
    else:
        # Staff and others can only see their own username
        users = User.objects.filter(id=request.user.id, created_denominations__isnull=False).distinct().values('id', 'username')
    
    return JsonResponse({'users': list(users)})


@login_required
def edit_denomination(request, key):
    """View and edit denomination by key"""
    denominations = Denomination.objects.filter(key=key).order_by('denomination')
    
    if not denominations.exists():
        messages.error(request, 'Denomination not found.')
        return redirect('entries:denominations')
    
    # Get the first record to extract metadata
    first_denom = denominations.first()
    time_period = first_denom.time_period
    created_by = first_denom.created_by
    created_at = first_denom.created_at
    
    # Authorization check: Only the creator can edit
    if created_by != request.user:
        raise PermissionDenied('You do not have permission to edit this denomination.')
    
    if request.method == 'POST':
        # Ensure time_period is in POST data (it should be from hidden input)
        post_data = request.POST.copy()
        if 'time_period' not in post_data:
            post_data['time_period'] = time_period
        
        form = DenominationForm(post_data)
        if form.is_valid():
            try:
                # Get form data
                note_2000 = form.cleaned_data.get('note_2000') or 0
                note_500 = form.cleaned_data.get('note_500') or 0
                note_200 = form.cleaned_data.get('note_200') or 0
                note_100 = form.cleaned_data.get('note_100') or 0
                note_50 = form.cleaned_data.get('note_50') or 0
                note_20 = form.cleaned_data.get('note_20') or 0
                note_10 = form.cleaned_data.get('note_10') or 0
                coins = form.cleaned_data.get('coins') or Decimal('0.00')
                damage = form.cleaned_data.get('damage') or Decimal('0.00')
                
                shop = form.cleaned_data.get('shop')

                # Create denomination map with new values
                denomination_updates = {
                    '2000': (note_2000, note_2000 * 2000),
                    '500': (note_500, note_500 * 500),
                    '200': (note_200, note_200 * 200),
                    '100': (note_100, note_100 * 100),
                    '50': (note_50, note_50 * 50),
                    '20': (note_20, note_20 * 20),
                    '10': (note_10, note_10 * 10),
                    'Coins': (1, coins),
                    'Damage': (1, damage),
                }
                
                # Update or create denominations
                for denom_name, (count, amount) in denomination_updates.items():
                    Denomination.objects.update_or_create(
                        key=key,
                        denomination=denom_name,
                        defaults={
                            'count': count,
                            'amount': Decimal(str(amount)),
                            'time_period': time_period,
                            'shop': shop,
                            'updated_by': request.user,
                            'created_by': created_by,
                        }
                    )
                
                logger.info(f"Denomination {key} updated by {request.user.username}")
                messages.success(request, 'Denomination updated successfully!')
                return redirect('entries:view_denomination', key=key)
            except Exception as e:
                logger.error(f"Error updating denomination {key} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, f'An error occurred while updating denomination: {str(e)}')
        else:
            messages.error(request, f'Please correct the errors in the form: {form.errors}')
    else:
        # Pre-populate form with existing data
        initial_data = {
            'time_period': time_period,
        }
        for denom in denominations:
            if denom.denomination == '2000':
                initial_data['note_2000'] = denom.count
            elif denom.denomination == '500':
                initial_data['note_500'] = denom.count
            elif denom.denomination == '200':
                initial_data['note_200'] = denom.count
            elif denom.denomination == '100':
                initial_data['note_100'] = denom.count
            elif denom.denomination == '50':
                initial_data['note_50'] = denom.count
            elif denom.denomination == '20':
                initial_data['note_20'] = denom.count
            elif denom.denomination == '10':
                initial_data['note_10'] = denom.count
            elif denom.denomination == 'Coins':
                initial_data['coins'] = denom.amount
            elif denom.denomination == 'Damage':
                initial_data['damage'] = denom.amount
        
        initial_data['shop'] = first_denom.shop
        form = DenominationForm(initial=initial_data)
    
    # Calculate total
    total = sum(d.amount for d in denominations)
    
    # Get the most recent updated_at timestamp
    updated_at = denominations.order_by('-updated_at').first().updated_at
    
    context = {
        'nav_title': 'Denomination',
        'form': form,
        'key': key,
        'time_period': time_period,
        'shop': first_denom.shop,
        'created_by': created_by,
        'created_at': created_at,
        'updated_at': updated_at,
        'total': total,
        'is_edit_mode': True,
    }
    return render(request, 'entries/denomination.html', context)


@login_required
def view_denomination(request, key):
    """View denomination by key (read-only)"""
    denominations = Denomination.objects.filter(key=key).order_by('denomination')
    
    if not denominations.exists():
        messages.error(request, 'Denomination not found.')
        return redirect('entries:denominations')
    
    # Get the first record to extract metadata
    first_denom = denominations.first()
    time_period = first_denom.time_period
    created_by = first_denom.created_by
    created_at = first_denom.created_at
    
    # Authorization check: Admin can view all, Staff can view only their own
    is_admin = request.user.groups.filter(name='Admin').exists() or request.user.is_superuser
    if not is_admin and created_by != request.user:
        raise PermissionDenied('You do not have permission to view this denomination.')
    
    # Pre-populate form with existing data (read-only)
    initial_data = {
        'time_period': time_period,
    }
    for denom in denominations:
        if denom.denomination == '2000':
            initial_data['note_2000'] = denom.count
        elif denom.denomination == '500':
            initial_data['note_500'] = denom.count
        elif denom.denomination == '200':
            initial_data['note_200'] = denom.count
        elif denom.denomination == '100':
            initial_data['note_100'] = denom.count
        elif denom.denomination == '50':
            initial_data['note_50'] = denom.count
        elif denom.denomination == '20':
            initial_data['note_20'] = denom.count
        elif denom.denomination == '10':
            initial_data['note_10'] = denom.count
        elif denom.denomination == 'Coins':
            initial_data['coins'] = denom.amount
        elif denom.denomination == 'Damage':
            initial_data['damage'] = denom.amount
    
    initial_data['shop'] = first_denom.shop
    form = DenominationForm(initial=initial_data)
    
    # Calculate total
    total = sum(d.amount for d in denominations)
    
    # Get the most recent updated_at timestamp
    updated_at = denominations.order_by('-updated_at').first().updated_at
    
    context = {
        'nav_title': 'Denomination',
        'form': form,
        'key': key,
        'time_period': time_period,
        'shop': first_denom.shop,
        'total': total,
        'is_view_mode': True,
    }
    return render(request, 'entries/denomination.html', context)


@login_required
def loan(request):
    if request.method == 'POST':
        pawn_no = request.POST.get('pawn_no')
        principal = request.POST.get('principal')
        interest = request.POST.get('interest')
        ledger_id = request.POST.get('ledger')
        loan_type = request.POST.get('loan_type')
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        
        try:
            ledger = Ledger.objects.get(id=ledger_id)
            principal_amount = Decimal(principal)
            interest_amount = Decimal(interest)

            # Resolve the chosen date+time (fallback to now)
            try:
                chosen_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localdate()
            except ValueError:
                chosen_date = timezone.localdate()
            try:
                chosen_time = datetime.strptime(time_str, '%H:%M').time() if time_str else timezone.localtime(timezone.now()).time()
            except ValueError:
                chosen_time = timezone.localtime(timezone.now()).time()
            chosen_dt = timezone.make_aware(datetime.combine(chosen_date, chosen_time))
            today = chosen_date
            
            with db_transaction.atomic():
                # Lock the shop for balance operations
                shop = Shop.objects.select_for_update().get(pk=ledger.shop_id)
                
                # --- Determine loan type labels ---
                if loan_type == 'LOAN':
                    if principal_amount > shop.balance:
                        messages.error(request, "Insufficient balance in shop")
                        return redirect('entries:add_entries')
                    name = 'LOAN'
                    tr_type = 'DEBIT'
                    principal_remark = 'Loan Principal'
                    interest_remark = 'Loan Interest'
                else:
                    name = 'RELEASE'
                    tr_type = 'CREDIT'
                    principal_remark = 'Release Principal'
                    interest_remark = 'Release Interest'
                
                # --- Check if a loan entry already exists for this type/ledger/date ---
                existing_loan = Loan.objects.filter(
                    ledger=ledger,
                    type=loan_type,
                    created_at__date=today
                ).first()
                
                if existing_loan:
                    # ── UPDATE existing loan entry ──
                    logger.info(f"Found existing {loan_type} entry for {ledger.name} on {today}. Updating...")
                    existing_loan.principal += principal_amount
                    existing_loan.interest += interest_amount
                    existing_loan.pawn_no = pawn_no
                    existing_loan.updated_by = request.user
                    existing_loan.save()
                else:
                    # ── CREATE new loan entry ──
                    loan_entry = Loan(
                        pawn_no=pawn_no,
                        ledger=ledger,
                        type=loan_type,
                        principal=principal_amount,
                        interest=interest_amount,
                        created_at=chosen_dt,
                        created_by=request.user,
                        updated_by=request.user
                    )
                    loan_entry.save()
                
                # ── PRINCIPAL transaction: find existing or create new ──
                existing_principal = Transactions.objects.filter(
                    shop=shop,
                    remarks=principal_remark,
                    created_at__date=today
                ).first()
                
                if existing_principal:
                    # Update existing principal transaction with additional amount
                    transaction_helper.update_transaction_amount(
                        txn=existing_principal,
                        additional_amount=principal_amount,
                        tr_type=tr_type,
                        user=request.user,
                    )
                    principal_new_balance = existing_principal.new_balance
                else:
                    # No principal transaction for this day – get old_balance from
                    # the most recent transaction *before* chosen_dt
                    principal_old_balance = transaction_helper.get_previous_balance(shop, chosen_dt)
                    principal_txn = transaction_helper.create_transaction(
                        shop=shop,
                        amount=principal_amount,
                        name=name,
                        tr_type=tr_type,
                        remarks=principal_remark,
                        old_balance=principal_old_balance,
                        chosen_dt=chosen_dt,
                        user=request.user,
                    )
                    existing_principal = principal_txn
                    principal_new_balance = principal_txn.new_balance
                
                # ── INTEREST transaction: find existing or create new ──
                existing_interest = Transactions.objects.filter(
                    shop=shop,
                    remarks=interest_remark,
                    created_at__date=today
                ).first()
                
                last_txn_for_cascade = None  # track which transaction to cascade from
                
                if existing_interest:
                    # Update existing interest transaction; also refresh its old_balance
                    # to match the (possibly changed) principal transaction's new_balance
                    transaction_helper.update_transaction_amount(
                        txn=existing_interest,
                        additional_amount=interest_amount,
                        tr_type='CREDIT',
                        user=request.user,
                        new_old_balance=principal_new_balance,
                    )
                    last_txn_for_cascade = existing_interest
                elif interest_amount > 0:
                    # Create new interest transaction whose old_balance = principal's new_balance
                    interest_txn = transaction_helper.create_transaction(
                        shop=shop,
                        amount=interest_amount,
                        name=name,
                        tr_type='CREDIT',
                        remarks=interest_remark,
                        old_balance=principal_new_balance,
                        chosen_dt=chosen_dt,
                        user=request.user,
                    )
                    last_txn_for_cascade = interest_txn
                else:
                    # No interest amount – cascade from the principal transaction
                    last_txn_for_cascade = existing_principal
                
                # ── CASCADE: update all subsequent transactions & shop balance ──
                transaction_helper.update_latest_transactions(
                    request,
                    last_txn_for_cascade,
                    last_txn_for_cascade.new_balance,
                )
                # After cascading, the final balance sits on _cascaded_balance;
                # update the shop to keep it in sync.
                final_balance = getattr(last_txn_for_cascade, '_cascaded_balance', last_txn_for_cascade.new_balance)
                shop.refresh_from_db()
                shop.balance = final_balance
                shop.save()
                
                action = 'updated' if existing_loan else 'created'
                messages.success(request, f'{loan_type.capitalize()} entry {action} successfully with transactions!')
                
        except Ledger.DoesNotExist:
            messages.error(request, 'Selected ledger does not exist.')
        except Exception as e:
            messages.error(request, f'Error creating loan entry: {str(e)}')
    
    return redirect('entries:add_entries')


@login_required
def loans(request):
    """View all loan transactions with pagination and filtering"""
    loans_list = Loan.objects.select_related('ledger', 'created_by', 'updated_by').order_by('-created_at')
    
    # Apply filters
    from_date = (request.GET.get('from_date') or '').strip()
    to_date = (request.GET.get('to_date') or '').strip()
    ledger_filter = (request.GET.get('ledger') or '').strip()
    type_filter = (request.GET.get('type') or '').strip().upper()
    search_query = (request.GET.get('search') or '').strip()

    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            loans_list = loans_list.filter(created_at__date__gte=from_date_obj)
        except ValueError:
            from_date = ''

    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            loans_list = loans_list.filter(created_at__date__lte=to_date_obj)
        except ValueError:
            to_date = ''

    if ledger_filter and ledger_filter.isdigit():
        loans_list = loans_list.filter(ledger_id=int(ledger_filter))
    elif ledger_filter:
        ledger_filter = ''

    if type_filter in ['LOAN', 'RELEASE']:
        loans_list = loans_list.filter(type=type_filter)
    else:
        type_filter = ''

    if search_query:
        loans_list = loans_list.filter(pawn_no__icontains=search_query)
    
    # Calculate totals
    loan_totals = loans_list.filter(type='LOAN').aggregate(
        total_principal=Sum('principal'),
        total_interest=Sum('interest')
    )
    release_totals = loans_list.filter(type='RELEASE').aggregate(
        total_principal=Sum('principal'),
        total_interest=Sum('interest')
    )
    
    # Pagination
    paginator = Paginator(loans_list, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all ledgers for filter dropdown
    all_ledgers = Ledger.objects.all().order_by('name')
    
    context = {
        'nav_title': 'Loan Transactions',
        'page_obj': page_obj,
        'all_ledgers': all_ledgers,
        'from_date': from_date,
        'to_date': to_date,
        'ledger_filter': ledger_filter,
        'type_filter': type_filter,
        'search_query': search_query,
        'loan_totals': loan_totals,
        'release_totals': release_totals,
        'all_loans': loans_list,  # For print view
        'is_admin_user': is_admin(request.user),
    }
    return render(request, 'entries/loans.html', context)


@login_required
def edit_loan(request, pk):
    """Edit a loan transaction"""
    loan = get_object_or_404(Loan, pk=pk)
    old_pawn_no = loan.pawn_no
    old_principal = loan.principal
    old_interest = loan.interest
    old_type = loan.type
    old_ledger = loan.ledger
    loan_created_date = timezone.localtime(loan.created_at).date()
    
    if request.method == 'POST':
        logger.info("************ Loan Updation Started ************")
        form = LoanEditForm(request.POST, instance=loan)
        if form.is_valid():
            updated_loan = form.save(commit=False)
            new_principal = updated_loan.principal
            new_interest = updated_loan.interest
            new_type = updated_loan.type
            new_ledger = updated_loan.ledger
            logger.info("Old Pawn No.: [" + str(old_pawn_no) + "] New Pawn No.: [" + str(updated_loan.pawn_no) + "]")
            logger.info("Old Principal: [" + str(old_principal) + "] New Principal: [" + str(new_principal) + "]")
            logger.info("Old Interest: [" + str(old_interest) + "] New Interest: [" + str(new_interest) + "]")
            logger.info("Old Type: [" + old_type  +"] New Type: [" + new_type + "]")
            logger.info("Old Ledger: [" + str(old_ledger)  +"] New Ledger: [" + str(new_ledger) + "]")
            
            if request.user.is_authenticated:
                updated_loan.updated_by = request.user
            
            try:
                with db_transaction.atomic():
                    # Find and update/delete old transactions based on original loan type
                    if old_type == 'LOAN':
                        old_principal_remark = 'Loan Principal'
                        old_interest_remark = 'Loan Interest'
                    else:  # RELEASE
                        old_principal_remark = 'Release Principal'
                        old_interest_remark = 'Release Interest'
                    
                    # Get old transactions (search by shop since transactions no longer have ledger FK)
                    old_shop = old_ledger.shop
                    new_shop_from_ledger = new_ledger.shop
                    logger.info(f"Searching for old principal transaction: shop={old_shop.name}, remark={old_principal_remark}, date={loan_created_date}")
                    old_principal_trans = Transactions.objects.filter(
                        shop=old_shop,
                        remarks=old_principal_remark,
                        created_at__date=loan_created_date
                    ).first()
                    logger.info(f"Old principal transaction found: {old_principal_trans is not None}")
                    
                    logger.info(f"Searching for old interest transaction: shop={old_shop.name}, remark={old_interest_remark}, date={loan_created_date}")
                    old_interest_trans = Transactions.objects.filter(
                        shop=old_shop,
                        remarks=old_interest_remark,
                        created_at__date=loan_created_date
                    ).first()
                    logger.info(f"Old interest transaction found: {old_interest_trans is not None}")
                    
                    # Lock the shop(s)
                    if old_shop.id == new_shop_from_ledger.id:
                        # Same shop - lock it
                        shop = Shop.objects.select_for_update().get(pk=old_shop.id)
                        
                        # Reverse old transactions
                        if old_principal_trans:
                            if old_type == 'LOAN':
                                shop.balance += old_principal  # Reverse DEBIT
                            else:
                                shop.balance -= old_principal  # Reverse CREDIT
                        
                        if old_interest_trans:
                            shop.balance -= old_interest  # Both types have CREDIT for interest
                        
                        logger.info("TEMP: Reversed Shop Balance: " + str(shop.balance))
                        # Apply new transactions
                        if new_type == 'LOAN':
                            # Check if debit amount exceeds balance
                            if new_principal > shop.balance:
                                form.add_error(None, f'Insufficient balance in {shop.name}. Available balance: {shop.balance}')
                                context = {
                                    'nav_title': 'Loan Transactions',
                                    'form': form,
                                    'loan': loan,
                                }
                                return render(request, 'entries/edit-loan.html', context)
                            
                            # Debit principal
                            old_balance = shop.balance
                            shop.balance -= new_principal
                            new_balance = shop.balance
                            
                            # Reverse Old Ledger Transaction Principal
                            logger.info("Old Ledger Transaction Principal: " + str(old_principal_trans.amount))
                            old_transaction_principal = old_principal_trans.amount - old_principal
                            logger.info("Reversed Old Ledger Transaction Principal: " + str(old_transaction_principal))
                            new_transaction_principal = old_transaction_principal + new_principal
                            logger.info("New Ledger Transaction Principal: " + str(new_transaction_principal))
                                
                            # Update or create principal transaction
                            if old_principal_trans and old_type == 'LOAN':
                                old_principal_trans.amount = new_transaction_principal
                                old_principal_trans.new_balance = new_balance
                                old_principal_trans.updated_by = request.user
                                old_principal_trans.save()
                            else:
                                transaction_helper.reverse_principal_transactions(request,old_principal_trans,old_principal,old_type)

                                Transactions.objects.create(
                                    amount=new_principal,
                                    name='Loan',
                                    shop=shop,
                                    tr_type='DEBIT',
                                    remarks='Loan Principal',
                                    old_balance=old_balance,
                                    new_balance=new_balance,
                                    created_by=request.user,
                                    created_at=old_principal_trans.created_at,
                                    updated_by=request.user
                                )
                            
                            # Credit interest
                            old_balance = shop.balance
                            shop.balance += new_interest
                            new_balance = shop.balance
                            
                            # Reverse Old Ledger Transaction Interest
                            logger.info("Old Ledger Transaction Interest: " + str(old_interest_trans.amount))
                            old_transaction_interest = old_interest_trans.amount - old_interest
                            logger.info("Reversed Old Ledger Transaction Interest: " + str(old_transaction_interest))
                            new_transaction_interest = old_transaction_interest + new_interest
                            logger.info("New Ledger Transaction Interest: " + str(new_transaction_interest))
                            
                            # Update or create interest transaction
                            if old_interest_trans and old_type == 'LOAN':                                
                                old_interest_trans.amount = new_transaction_interest
                                old_interest_trans.new_balance = new_balance
                                old_interest_trans.updated_by = request.user
                                old_interest_trans.save()
                            else:
                                old_interest_trans.amount = old_interest_trans.amount - old_interest
                                old_interest_trans.new_balance = old_interest_trans.new_balance - old_interest
                                old_interest_trans.updated_by = request.user
                                old_interest_trans.save()
                                
                                Transactions.objects.create(
                                    amount=new_interest,
                                    name='Loan',
                                    shop=shop,
                                    tr_type='CREDIT',
                                    remarks='Loan Interest',
                                    old_balance=old_balance,
                                    new_balance=new_balance,
                                    created_by=request.user,
                                    created_at=old_principal_trans.created_at,
                                    updated_by=request.user
                                )
                        else:  # RELEASE
                            # Credit principal
                            old_balance = shop.balance
                            shop.balance += new_principal
                            new_balance = shop.balance
                            
                            # Reverse Old Ledger Transaction Principal
                            logger.info("Old Ledger Transaction Principal: " + str(old_principal_trans.amount))
                            old_transaction_principal = old_principal_trans.amount - old_principal
                            logger.info("Reversed Old Ledger Transaction Principal: " + str(old_transaction_principal))
                            new_transaction_principal = old_transaction_principal + new_principal
                            logger.info("New Ledger Transaction Principal: " + str(new_transaction_principal))
                            
                            # Update or create principal transaction
                            if old_principal_trans and old_type == 'RELEASE':
                                old_principal_trans.amount = new_transaction_principal
                                old_principal_trans.new_balance = new_balance
                                old_principal_trans.updated_by = request.user
                                old_principal_trans.save()
                            else:
                                transaction_helper.reverse_principal_transactions(request,old_principal_trans,old_principal,old_type)
                                
                                Transactions.objects.create(
                                    amount=new_principal,
                                    name='Release',
                                    shop=shop,
                                    tr_type='CREDIT',
                                    remarks='Release Principal',
                                    old_balance=old_balance,
                                    new_balance=new_balance,
                                    created_by=request.user,
                                    created_at=old_principal_trans.created_at,
                                    updated_by=request.user
                                )
                            
                            # Credit interest
                            old_balance = shop.balance
                            shop.balance += new_interest
                            new_balance = shop.balance
                            
                            # Reverse Old Ledger Transaction Interest
                            logger.info("Old Ledger Transaction Interest: " + str(old_interest_trans.amount))
                            old_transaction_interest = old_interest_trans.amount - old_interest
                            logger.info("Reversed Old Ledger Transaction Interest: " + str(old_transaction_interest))
                            new_transaction_interest = old_transaction_interest + new_interest
                            logger.info("New Ledger Transaction Interest: " + str(new_transaction_interest))
                            
                            # Update or create interest transaction
                            if old_interest_trans and old_type == 'RELEASE':                                
                                old_interest_trans.amount = new_transaction_interest
                                old_interest_trans.new_balance = new_balance
                                old_interest_trans.updated_by = request.user
                                old_interest_trans.save()
                            else:
                                old_interest_trans.amount = old_interest_trans.amount - old_interest
                                old_interest_trans.old_balance = old_principal_trans.new_balance
                                old_interest_trans.new_balance = old_interest_trans.old_balance + old_interest_trans.amount
                                old_interest_trans.updated_by = request.user
                                old_interest_trans.save()
                                    
                                Transactions.objects.create(
                                    amount=new_interest,
                                    name='Release',
                                    shop=shop,
                                    tr_type='CREDIT',
                                    remarks='Release Interest',
                                    old_balance=old_balance,
                                    new_balance=new_balance,
                                    created_by=request.user,
                                    created_at=old_principal_trans.created_at,
                                    updated_by=request.user
                                )
                        if old_principal_trans.amount == 0:
                            old_principal_trans.delete()
                        if old_interest_trans.amount == 0:
                            old_interest_trans.delete()
                        shop.save()
                    else:
                        logger.info("Updating Shop in Loan Transaction")
                        # Different shops - lock both
                        shop_ids = list(set([old_shop.id, new_shop_from_ledger.id]))
                        shops = {s.pk: s for s in Shop.objects.select_for_update().filter(pk__in=shop_ids)}
                        old_shop_obj = shops[old_shop.id]
                        new_shop_obj = shops[new_shop_from_ledger.id]
                        
                        if new_type == 'LOAN':
                            new_principal_remark = 'Loan Principal'
                            new_interest_remark = 'Loan Interest'
                        else:  # RELEASE
                            new_principal_remark = 'Release Principal'
                            new_interest_remark = 'Release Interest'
                        
                        new_principal_trans = Transactions.objects.filter(
                            shop=new_shop_obj,
                            remarks=new_principal_remark,
                            created_at__date=loan_created_date
                        ).first()
                        
                        new_interest_trans = Transactions.objects.filter(
                            shop=new_shop_obj,
                            remarks=new_interest_remark,
                            created_at__date=loan_created_date
                        ).first()
                        
                        # Reverse old transactions on old shop
                        logger.info(f"About to reverse old transactions - Principal: {old_principal_trans is not None}, Interest: {old_interest_trans is not None}")
                        if old_principal_trans:
                            logger.info("Trying to reverse old shop transaction")
                            if old_type == 'LOAN':
                                old_shop_obj.balance += old_principal
                                old_principal_trans.new_balance = old_principal_trans.new_balance + old_principal
                            else:
                                old_shop_obj.balance -= old_principal
                                old_principal_trans.new_balance = old_principal_trans.new_balance - old_principal
                                
                            # Reverse Old Transaction Principal
                            logger.info("Old Transaction Principal: " + str(old_principal_trans.amount))
                            old_transaction_principal = old_principal_trans.amount - old_principal
                            logger.info("Reversed Old Transaction Principal: " + str(old_transaction_principal))
                            new_transaction_principal = old_transaction_principal + new_principal
                            logger.info("New Transaction Principal: " + str(new_transaction_principal))
                            
                            if (old_principal_trans.amount - old_principal) == 0:
                                old_principal_trans.delete()
                            else:
                                old_principal_trans.amount = old_principal_trans.amount - old_principal
                                old_principal_trans.updated_by = request.user
                                old_principal_trans.save()
                        else:
                            logger.warning(f"Old principal transaction NOT FOUND for reversal! Shop: {old_shop.name}, Remark: {old_principal_remark}, Date: {loan_created_date}")
                            logger.warning(f"All transactions for this shop on this date: {Transactions.objects.filter(shop=old_shop, created_at__date=loan_created_date).values_list('remarks', 'amount', 'tr_type')}")
                        
                        if old_interest_trans:
                            old_shop_obj.balance -= old_interest
                            if (old_interest_trans.amount - old_interest) == 0:
                                old_interest_trans.delete()
                            else:
                                old_interest_trans.amount = old_interest_trans.amount - old_interest
                                if old_principal_trans:
                                    old_interest_trans.old_balance = old_principal_trans.new_balance
                                else:
                                    old_interest_trans.old_balance = old_shop_obj.balance - old_interest_trans.amount
                                old_interest_trans.new_balance = old_interest_trans.new_balance - old_principal
                                old_interest_trans.updated_by = request.user
                                old_interest_trans.save()
                        else:
                            logger.warning(f"Old interest transaction NOT FOUND for reversal! Shop: {old_shop.name}, Remark: {old_interest_remark}, Date: {loan_created_date}")
                        
                        old_shop_obj.save()
                        
                        # Refresh new_shop_obj if same as old_shop_obj
                        if old_shop_obj.pk == new_shop_obj.pk:
                            new_shop_obj = old_shop_obj
                        
                        # Apply new transactions on new shop
                        if new_type == 'LOAN':
                            # Check if debit amount exceeds balance
                            if new_principal > new_shop_obj.balance:
                                form.add_error(None, f'Insufficient balance in {new_shop_obj.name}. Available balance: {new_shop_obj.balance}')
                                context = {
                                    'nav_title': 'Loan Transactions',
                                    'form': form,
                                    'loan': loan,
                                }
                                return render(request, 'entries/edit-loan.html', context)
                            
                            # Debit principal
                            old_balance = new_shop_obj.balance
                            new_shop_obj.balance -= new_principal
                            new_balance = new_shop_obj.balance
                            
                            if not new_principal_trans:
                                Transactions.objects.create(
                                    amount=new_principal,
                                    name='Loan',
                                    shop=new_shop_obj,
                                    tr_type='DEBIT',
                                    remarks='Loan Principal',
                                    old_balance=old_balance,
                                    new_balance=new_balance,
                                    created_by=request.user,
                                    created_at=old_principal_trans.created_at,
                                    updated_by=request.user
                                )
                            
                            # Credit interest
                            old_balance = new_shop_obj.balance
                            new_shop_obj.balance += new_interest
                            new_balance = new_shop_obj.balance
                            
                            if not new_interest_trans:
                                Transactions.objects.create(
                                    amount=new_interest,
                                    name='Loan',
                                    shop=new_shop_obj,
                                    tr_type='CREDIT',
                                    remarks='Loan Interest',
                                    old_balance=old_balance,
                                    new_balance=new_balance,
                                    created_by=request.user,
                                    created_at=old_principal_trans.created_at,
                                    updated_by=request.user
                                )
                        else:  # RELEASE
                            # Credit principal
                            old_balance = new_shop_obj.balance
                            new_shop_obj.balance += new_principal
                            new_balance = new_shop_obj.balance
                            
                            if not new_principal_trans:
                                Transactions.objects.create(
                                    amount=new_principal,
                                    name='Release',
                                    shop=new_shop_obj,
                                    tr_type='CREDIT',
                                    remarks='Release Principal',
                                    old_balance=old_balance,
                                    new_balance=new_balance,
                                    created_by=request.user,
                                    created_at=old_principal_trans.created_at,
                                    updated_by=request.user
                                )
                            
                            # Credit interest
                            old_balance = new_shop_obj.balance
                            new_shop_obj.balance += new_interest
                            new_balance = new_shop_obj.balance
                            
                            if not new_interest_trans:
                                Transactions.objects.create(
                                    amount=new_interest,
                                    name='Release',
                                    shop=new_shop_obj,
                                    tr_type='CREDIT',
                                    remarks='Release Interest',
                                    old_balance=old_balance,
                                    new_balance=new_balance,
                                    created_by=request.user,
                                    created_at=old_principal_trans.created_at,
                                    updated_by=request.user
                                )
                        
                        if new_principal_trans:
                            new_principal_trans.amount = new_principal_trans.amount + new_principal
                            new_principal_trans.old_balance = old_balance
                            new_principal_trans.new_balance = new_balance
                            new_principal_trans.updated_by = request.user
                            new_principal_trans.save()
                        
                        if new_interest_trans:
                            new_interest_trans.amount = new_interest_trans.amount + new_interest
                            new_interest_trans.old_balance = old_balance
                            new_interest_trans.new_balance = new_balance
                            new_interest_trans.updated_by = request.user
                            new_interest_trans.save()
                        
                        new_shop_obj.save()
                        
                    # Save the updated loan
                    updated_loan.save()

                    # Apply chosen date+time to created_at
                    chosen_date = form.cleaned_data.get('date')
                    if chosen_date:
                        chosen_time = form.cleaned_data.get('time') or timezone.localtime(timezone.now()).time()
                        chosen_dt = timezone.make_aware(
                            datetime.combine(chosen_date, chosen_time)
                        )
                        Loan.objects.filter(pk=updated_loan.pk).update(
                            created_at=chosen_dt,
                        )
                    
                    logger.info(f"Loan updated by {request.user.username}: ID {pk}, Type {new_type}, Pawn No {updated_loan.pawn_no}")
                    messages.success(request, 'Loan transaction and associated ledger transactions updated successfully!')
                    return redirect('entries:loans')
                    
            except Exception as e:
                logger.error(f"Error updating loan {pk} by {request.user.username}: {str(e)}", exc_info=True)
                messages.error(request, f'An error occurred while updating loan: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoanEditForm(
            instance=loan,
            initial={'date': timezone.localtime(loan.created_at).date(), 'time': timezone.localtime(loan.created_at).time().replace(second=0, microsecond=0)},
        )
    
    context = {
        'nav_title': 'Loan Transactions',
        'form': form,
        'loan': loan,
    }
    return render(request, 'entries/edit-loan.html', context)


@login_required
@admin_required
def delete_loan(request, pk):
    """Delete a loan transaction (admin only)"""
    loan = get_object_or_404(Loan, pk=pk)
    
    if request.method == 'POST':
        loan_id = loan.id
        loan_pawn_no = loan.pawn_no
        loan_type = loan.type
        loan_ledger = loan.ledger
        loan_created_date = timezone.localtime(loan.created_at).date()
        
        try:
            with db_transaction.atomic():
                # Lock the shop
                ledger = Ledger.objects.get(pk=loan_ledger.id)
                shop = Shop.objects.select_for_update().get(pk=ledger.shop_id)
                
                # Determine remarks based on loan type
                if loan_type == 'LOAN':
                    principal_remark = 'Loan Principal'
                    interest_remark = 'Loan Interest'
                else:  # RELEASE
                    principal_remark = 'Release Principal'
                    interest_remark = 'Release Interest'
                
                # Find associated transactions
                principal_trans = Transactions.objects.filter(
                    shop=shop,
                    remarks=principal_remark,
                    created_at__date=loan_created_date
                ).first()
                
                
                # Reverse transaction effects on shop balance
                if principal_trans:
                    if loan_type == 'LOAN':
                        # Reverse DEBIT - add back to balance
                        shop.balance += loan.principal
                    else:  
                        # RELEASE
                        # Reverse CREDIT - subtract from balance
                        shop.balance -= loan.principal
                    if (principal_trans.amount - loan.principal) == 0:
                        transaction_helper.update_latest_transactions(request,principal_trans,principal_trans.new_balance)
                        principal_trans.delete()
                        logger.info(f"Deleted {principal_remark} transaction for loan {loan_id}")
                    else:
                        principal_trans.amount = principal_trans.amount - loan.principal
                        principal_trans.new_balance = principal_trans.new_balance + loan.principal
                        principal_trans.save()
                        transaction_helper.update_latest_transactions(request,principal_trans,principal_trans.new_balance)
                        logger.info(f"Updated {principal_remark} transaction for loan {loan_id}")
                    
                
                interest_trans = Transactions.objects.filter(
                    shop=shop,
                    remarks=interest_remark,
                    created_at__date=loan_created_date
                ).first()
                
                if interest_trans:
                    # Both loan and release have CREDIT for interest
                    shop.balance -= loan.interest
                    if (interest_trans.amount - loan.interest) == 0:
                        transaction_helper.update_latest_transactions(request,interest_trans,interest_trans.new_balance)
                        interest_trans.delete()
                        logger.info(f"Deleted {interest_remark} transaction for loan {loan_id}")
                    else:
                        interest_trans.amount = interest_trans.amount - loan.interest
                        interest_trans.new_balance = principal_trans.new_balance + interest_trans.amount
                        interest_trans.save()
                        transaction_helper.update_latest_transactions(request,interest_trans,interest_trans.new_balance)
                        logger.info(f"Updated {interest_remark} transaction for loan {loan_id}")
                
                # Save updated shop balance
                shop.save()
                
                # Delete the loan entry
                loan.delete()
                logger.warning(f"Loan deleted by {request.user.username}: ID {loan_id}, Type {loan_type}, Pawn No {loan_pawn_no}")
                messages.success(request, 'Loan transaction and associated ledger transactions deleted successfully!')
        except Exception as e:
            logger.error(f"Error deleting loan {loan_id} by {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting loan.')
        
        return redirect('entries:loans')
    
    context = {
        'nav_title': 'Loan Transactions',
        'loan': loan,
    }
    return render(request, 'entries/delete-loan.html', context)


@login_required
@admin_required
def transaction_history(request, pk):
    """Show current transaction and full audit history for a transaction record."""
    transaction = get_object_or_404(
        Transactions.objects.select_related('shop', 'created_by', 'updated_by'),
        pk=pk
    )
    history_records = transaction.history.all().order_by('-history_date')

    context = {
        'nav_title': 'Other Transactions',
        'transaction': transaction,
        'history_records': history_records,
    }
    return render(request, 'entries/transaction_history.html', context)


@login_required
@admin_required
def loan_history(request, pk):
    """Show current loan entry and full audit history for a loan record."""
    loan = get_object_or_404(
        Loan.objects.select_related('ledger', 'created_by', 'updated_by'),
        pk=pk
    )
    history_records = loan.history.all().order_by('-history_date')

    context = {
        'nav_title': 'Loan Transactions',
        'loan': loan,
        'history_records': history_records,
    }
    return render(request, 'entries/loan_history.html', context)


def custom_404_view(request, exception=None):
    """Custom 404 error handler that properly passes request context"""
    return render(request, '404.html', status=404)


def custom_403_view(request, exception=None):
    """Custom 403 error handler for permission denied"""
    return render(request, '403.html', status=403)
