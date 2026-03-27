from datetime import datetime, timedelta
from decimal import Decimal
import csv
import logging
import time
import openpyxl
from functools import wraps
from openpyxl.styles import Font, Alignment, PatternFill

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction as db_transaction
from django.db.models import Case, DecimalField, F, Min, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import requests

from .forms import TransactionForm, TransferForm, DenominationForm, LoanForm, LoanEditForm
from .models import Transactions, Denomination, Loan
from manager.models import Shop, Ledger, Configuration
from .helpers import transactions as transaction_helper
from manager.helper.manager_helper import log_activity

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
def home(request):
    today = timezone.localdate()
    transactions = Transactions.objects.filter(transaction_dt__date=today).order_by('-transaction_dt')[:10]
    daily_totals = (
        Transactions.objects.filter(transaction_dt__date=today)
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
        data = transaction_helper.get_opening_balance(shop, today)  # This will calculate and cache opening balance for the shop
        
        shop_balances.append({
            'shop': shop,
            'opening_balance': data['opening_balance'],
            'closing_balance': data['closing_balance'],
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
    """Add a new transaction entry"""
    form          = TransactionForm()
    transfer_form = TransferForm()
    loan_form     = LoanForm()

    if request.method == 'POST':
        form = TransactionForm(request.POST)

        if form.is_valid():
            transaction = form.save(commit=False)

            if request.user.is_authenticated:
                transaction.created_by = request.user
                transaction.updated_by = request.user

            # ── Resolve transaction date + time ──────────────────────
            chosen_date = form.cleaned_data.get('date')
            chosen_time = form.cleaned_data.get('time') or timezone.localtime(timezone.now()).time()
            transaction.transaction_dt = timezone.make_aware(
                datetime.combine(chosen_date, chosen_time)
            )

            logger.info("============ Transaction Creation Started ============")
            logger.info(f"Transaction -> type=[{transaction.tr_type}] | amount=[{transaction.amount}] | date=[{transaction.transaction_dt}]")

            try:
                with db_transaction.atomic():
                    shop = Shop.objects.select_for_update().get(pk=transaction.shop_id)
                    logger.info(f"Shop -> name=[{shop.short_name}]")

                    # ── Balance check for DEBIT ───────────────────────
                    if transaction.tr_type == 'DEBIT':
                        available = transaction_helper.get_balance(shop, chosen_date)
                        logger.info(f"Balance check -> available=[{available}] | required=[{transaction.amount}]")
                        if transaction.amount > available:
                            form.add_error(None, f'Insufficient balance in {shop.short_name}. Available: {available}')
                            return render(request, 'entries/add_entries.html', {
                                'nav_title': 'Add Entries',
                                'form': form,
                                'transfer_form': TransferForm(),
                                'loan_form': LoanForm(),
                            })

                    # ── Save transaction ──────────────────────────────
                    transaction.save()
                    logger.info(f"Transaction [{transaction.id}] created -> type=[{transaction.tr_type}] | amount=[{transaction.amount}] | shop=[{shop.short_name}]")
                log_activity(request, 'CREATE', 'Transaction', transaction.id, f'Transaction created: {transaction.name} ({transaction.amount} {transaction.tr_type}) for {shop.short_name}')
                logger.info("============ Transaction Creation Completed ============")
                messages.success(request, 'Transaction added successfully!')

            except Exception as e:
                logger.error(f"Error creating transaction by [{request.user.username}]: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while creating transaction.')
                return render(request, 'entries/add_entries.html', {
                    'nav_title': 'Add Entries',
                    'form': form,
                    'transfer_form': TransferForm(),
                    'loan_form': LoanForm(),
                })

            return redirect('entries:add_entries')

        else:
            logger.warning(f"Transaction form invalid -> errors=[{form.errors}]")

    return render(request, 'entries/add_entries.html', {
        'nav_title': 'Add Entries',
        'form': form,
        'transfer_form': transfer_form,
        'loan_form': loan_form,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })

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
                        messages.error(request, f'Insufficient balance in {from_shop.short_name}. Current balance: {from_shop.balance}')
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
@ensure_csrf_cookie
def transactions(request):
    # Get filter parameters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    shop_filter = request.GET.get('shop')
    type_filter = request.GET.get('type')
    search_query = request.GET.get('search', '')
    name_search_query = request.GET.get('name_search', '')
    
    transactions_list = Transactions.objects.all().select_related(
            'shop', 'created_by', 'updated_by'
        ).order_by('-transaction_dt')

    # Apply filters
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            transactions_list = transactions_list.filter(transaction_dt__date__gte=from_date_obj)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            transactions_list = transactions_list.filter(transaction_dt__date__lte=to_date_obj)
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
    paginator = Paginator(transactions_list, 15)  # Show 15 transactions per page
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
    
    if request.headers.get('HX-Request'):
        return render(request, 'entries/partials/transaction_rows.html', {
            'page_obj': page_obj,
            'is_super_admin': request.user.is_superuser,
            'is_admin': is_admin(request.user),
            'is_admin_user': is_admin(request.user) or request.user.is_superuser,
        })

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
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'is_admin_user': is_admin(request.user) or request.user.is_superuser,
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
    transactions_list = Transactions.objects.select_related('shop', 'created_by', 'updated_by').order_by('-transaction_dt','-updated_at')
    
    # Apply filters
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            transactions_list = transactions_list.filter(transaction_dt__date__gte=from_date_obj)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            transactions_list = transactions_list.filter(transaction_dt__date__lte=to_date_obj)
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
            transaction.transaction_dt.strftime('%Y-%m-%d'),
            transaction.transaction_dt.strftime('%H:%M:%S'),
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
        ws.cell(row=current_row, column=1, value=transaction.transaction_dt.strftime('%Y-%m-%d'))
        ws.cell(row=current_row, column=2, value=transaction.transaction_dt.strftime('%H:%M:%S'))
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
    """Edit an existing transaction"""
    transaction = get_object_or_404(Transactions, pk=pk)

    # ── Snapshot old values ──────────────────────────────────────────
    old_amount  = transaction.amount
    old_type    = transaction.tr_type
    old_shop    = transaction.shop
    old_date    = timezone.localtime(transaction.transaction_dt).date()

    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction)

        if form.is_valid():
            updated_transaction = form.save(commit=False)

            if request.user.is_authenticated:
                updated_transaction.updated_by = request.user

            # ── Resolve new transaction date + time ──────────────────
            chosen_date = form.cleaned_data.get('date')
            chosen_time = form.cleaned_data.get('time') or timezone.localtime(timezone.now()).time()
            updated_transaction.transaction_dt = timezone.make_aware(
                datetime.combine(chosen_date, chosen_time)
            )
            new_date = chosen_date
            new_shop = updated_transaction.shop
            new_type = updated_transaction.tr_type
            new_amount = updated_transaction.amount

            logger.info("============ Transaction Update Started ============")
            logger.info(f"Old -> amount=[{old_amount}] | type=[{old_type}] | shop=[{old_shop}] | date=[{old_date}]")
            logger.info(f"New -> amount=[{new_amount}] | type=[{new_type}] | shop=[{new_shop}] | date=[{new_date}]")

            try:
                with db_transaction.atomic():

                    # ── Balance check for DEBIT ───────────────────────
                    if new_type == 'DEBIT':
                        available = transaction_helper.get_balance(new_shop, new_date)
                        # Add back old amount if same shop to avoid double counting
                        if old_shop.id == new_shop.id and old_type == 'DEBIT':
                            available += old_amount
                        logger.info(f"Balance check -> shop=[{new_shop.short_name}] | available=[{available}] | required=[{new_amount}]")
                        if new_amount > available:
                            form.add_error(None, f'Insufficient balance in {new_shop.short_name} on {new_date}. Available: {available}')
                            return render(request, 'entries/edit-transaction.html', {
                                'nav_title': 'Other Transactions',
                                'form': form,
                                'transaction': transaction,
                            })

                    # ── Save updated transaction ──────────────────────
                    updated_transaction.save()
                    logger.info(f"Transaction [{pk}] updated successfully")

                # ── Build change summary ──────────────────────────────
                changes = []
                if old_amount != new_amount:
                    changes.append(f"amount: [{old_amount}] -> [{new_amount}]")
                if old_type != new_type:
                    changes.append(f"type: [{old_type}] -> [{new_type}]")
                if old_shop.id != new_shop.id:
                    changes.append(f"shop: [{old_shop.short_name}] -> [{new_shop.short_name}]")
                if old_date != new_date:
                    changes.append(f"date: [{old_date}] -> [{new_date}]")
                logger.info(f"Transaction [{pk}] changes -> {', '.join(changes) if changes else 'no changes'}")
                logger.info("============ Transaction Update Completed ============")
                messages.success(request, 'Transaction updated successfully!')

            except Exception as e:
                logger.error(f"Error editing transaction [{pk}] by [{request.user.username}]: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while editing transaction.')
                return render(request, 'entries/edit-transaction.html', {
                    'nav_title': 'Other Transactions',
                    'form': form,
                    'transaction': transaction,
                })
            log_activity(request, 'UPDATE', 'Transaction', transaction.id, f'Transaction updated: {transaction.name} ({transaction.amount} {transaction.tr_type}) for {transaction.shop.short_name}')
            return redirect('entries:transactions')

        else:
            logger.warning(f"Transaction form invalid -> errors=[{form.errors}]")

    else:
        form = TransactionForm(
            instance=transaction,
            initial={
                'date': timezone.localtime(transaction.transaction_dt).date(),
                'time': timezone.localtime(transaction.transaction_dt).time().replace(second=0, microsecond=0),
            }
        )

    return render(request, 'entries/edit-transaction.html', {
        'nav_title': 'Other Transactions',
        'form': form,
        'transaction': transaction,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })

@login_required
@csrf_protect
@admin_required
def delete_transaction(request, pk):
    """Delete a transaction (admin only)"""
    transaction = get_object_or_404(Transactions, pk=pk)

    if request.method == 'POST':
        transaction_id   = transaction.id
        transaction_amount = transaction.amount
        transaction_type = transaction.tr_type
        shop_name        = transaction.shop.short_name
        transaction_date = timezone.localtime(transaction.transaction_dt).date()

        logger.info("============ Transaction Deletion Started ============")
        logger.info(f"Transaction -> id=[{transaction_id}] | type=[{transaction_type}] | amount=[{transaction_amount}] | shop=[{shop_name}] | date=[{transaction_date}]")

        try:
            # Option 1 — warn user if transaction is loan-linked
            LOAN_REMARKS = ['Loan Principal', 'Loan Interest', 'Release Principal', 'Release Interest']
            with db_transaction.atomic():
                if transaction.remarks in LOAN_REMARKS:
                    messages.error(request, 'This transaction is linked to a loan entry. Please delete it from Loan Transactions page instead.')
                    return redirect('entries:transactions')
                log_activity(request, 'DELETE', 'Transaction', transaction.id, f'Transaction deleted: {transaction.name} ({transaction.amount} {transaction.tr_type}) for {transaction.shop.short_name}')
                transaction.delete()
                logger.warning(f"Transaction deleted by [{request.user.username}] -> id=[{transaction_id}] | type=[{transaction_type}] | amount=[{transaction_amount}] | shop=[{shop_name}]")
            messages.success(request, 'Transaction deleted successfully!')
            logger.info("============ Transaction Deletion Completed ============")

        except Exception as e:
            logger.error(f"Error deleting transaction [{transaction_id}] by [{request.user.username}]: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting transaction.')

        return redirect('entries:transactions')

    return render(request, 'entries/delete-transaction.html', {
        'nav_title': 'Other Transactions',
        'transaction': transaction,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })


@login_required
def report(request):
    # Get filter parameters
    report_date = request.GET.get('date')
    shop_id = request.GET.get('shop')
    all_configs = Configuration.objects.all()
    
    # Use today's date if no date specified
    if not report_date:
        report_date = timezone.localdate()
    else:
        # Convert string date to date object for template rendering
        try:
            report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
        except ValueError:
            report_date = timezone.localdate()
    
    next_day = report_date + timedelta(days=1)
    prev_day = report_date - timedelta(days=1)
    
    # Log report generation
    filter_info = f"shop_id={shop_id}" if shop_id else "all shops"
    logger.info(f"Report generated by {request.user.username}: date={report_date}, filter={filter_info}")
    
    # Base queryset - filter by date
    transactions = Transactions.objects.filter(
        transaction_dt__date=report_date
    ).select_related('shop', 'created_by', 'updated_by')
    
    # Apply shop filter if specified
    if shop_id:
        transactions = transactions.filter(shop_id=shop_id)
    
    transactions = transactions.order_by('transaction_dt')
    
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
        data = transaction_helper.get_opening_balance(shop, report_date)
        
        shop_summaries.append({
            'shop': shop,
            'opening_balance': data['opening_balance'],
            'closing_balance': data['closing_balance'],
            'debit_total': data['day_total_debit'],
            'credit_total': data['day_total_credit'],
        })
    
    all_shops = Shop.objects.all().order_by('name')
    
    # Get loan and release summaries for the report date
    loan_entries = Loan.objects.filter(
        type='LOAN',
        transaction_dt__date=report_date
    ).values('pawn_no', 'principal', 'interest')
    
    release_entries = Loan.objects.filter(
        type='RELEASE',
        transaction_dt__date=report_date
    ).values('pawn_no', 'principal', 'interest')
    
    # Calculate totals for loans
    loan_totals = Loan.objects.filter(
        type='LOAN',
        transaction_dt__date=report_date
    ).aggregate(
        total_principal=Coalesce(Sum('principal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_interest=Coalesce(Sum('interest'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
    )
    
    # Calculate totals for releases
    release_totals = Loan.objects.filter(
        type='RELEASE',
        transaction_dt__date=report_date
    ).aggregate(
        total_principal=Coalesce(Sum('principal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_interest=Coalesce(Sum('interest'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
    )
    
    # Fetch denominations for the current user on the report date, grouped by time period
    TIME_PERIOD_ORDER = {'MORNING': 1, 'AFTERNOON': 2, 'EVENING': 3, 'NIGHT': 4}
    if is_admin(request.user) or is_super_admin(request.user):
        denom_filter = {'created_at__date': report_date}
    else:
        denom_filter = {'created_by': request.user, 'created_at__date': report_date}
    
    if shop_id:
        denom_filter['shop_id'] = shop_id
    denomination_entries_qs = (
        Denomination.objects
        .filter(**denom_filter)
        .values('time_period', 'denomination', 'count', 'amount', 'shop__name','created_by__first_name','created_by__last_name')
        .order_by('time_period', 'denomination')
    )
    # Group denominations by time_period
    denomination_by_period = {}
    for entry in denomination_entries_qs:
        period    = entry['time_period']
        user_name = f"{entry.get('created_by__first_name') or ''} {entry.get('created_by__last_name') or ''}".strip()
        shop_name = entry.get('shop__name') or ''

        # Use (period, user, shop) as key to avoid mixing different users' same period
        group_key = (period, user_name, shop_name)

        if group_key not in denomination_by_period:
            denomination_by_period[group_key] = {
                'period':    period,
                'rows':      [],
                'total':     Decimal('0.00'),
                'shop_name': shop_name,
                'user':      user_name,
            }
        denomination_by_period[group_key]['rows'].append(entry)
        denomination_by_period[group_key]['total'] += entry['amount']
    # Sort periods by natural order
    denomination_periods = sorted(
        denomination_by_period.items(),
        key=lambda x: TIME_PERIOD_ORDER.get(x[0], 99)
    )
    
    configs={}
    for config in all_configs:
        if 'D_REP' in config.key:
            configs[config.key] = config.value
            print(f"Config: {config.key} = {config.value}")

    context = {
        'nav_title': 'Report',
        'transactions': transactions,
        'all_shops': all_shops,
        'configs': configs,
        'report_date': report_date,
        'selected_shop': shop_id,
        'debit_total': round(totals['debit_total'], 2),
        'credit_total': round(totals['credit_total'], 2),
        'shop_summaries': shop_summaries,
        'loan_entries': loan_entries,
        'release_entries': release_entries,
        'loan_totals': loan_totals,
        'release_totals': release_totals,
        'denomination_periods': denomination_periods,
        'next_day': next_day,
        'prev_day': prev_day,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
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
        transaction_dt__date=report_date
    ).select_related('shop', 'created_by', 'updated_by')
    
    if shop_id:
        transactions = transactions.filter(shop_id=shop_id)
    
    transactions = transactions.order_by('transaction_dt')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transaction_report_{report_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'Shop', 'Name', 'Remarks', 'DEBIT', 'CREDIT', 'Created By', 'Updated By'])
    
    for transaction in transactions:
        debit = transaction.amount if transaction.tr_type == 'DEBIT' else ''
        credit = transaction.amount if transaction.tr_type == 'CREDIT' else ''
        writer.writerow([
            transaction.transaction_dt.strftime('%Y-%m-%d'),
            transaction.transaction_dt.strftime('%H:%M:%S'),
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
        transaction_dt__date=report_date
    ).select_related('shop', 'created_by', 'updated_by')
    
    if shop_id:
        transactions = transactions.filter(shop_id=shop_id)
    
    transactions = transactions.order_by('transaction_dt')
    
    # Calculate shop balances
    shop_summaries = []
    shops_to_process = Shop.objects.filter(id=shop_id) if shop_id else Shop.objects.all()
    
    for shop in shops_to_process.order_by('name'):
        # Get first transaction of the day for this shop to fetch opening balance
        first_transaction = Transactions.objects.filter(
            shop=shop,
            transaction_dt__date=report_date
        ).order_by('transaction_dt').first()
        
        if first_transaction and first_transaction.old_balance is not None:
            opening_balance = first_transaction.old_balance
        else:
            # No transactions on this date, get last transaction before this date
            last_transaction = Transactions.objects.filter(
                shop=shop,
                transaction_dt__date__lt=report_date
            ).order_by('-transaction_dt').first()
            
            if last_transaction and last_transaction.new_balance is not None:
                opening_balance = last_transaction.new_balance
            else:
                # No transactions before this date, opening balance = 0
                opening_balance = '0.00'
        
        shop_day_transactions = Transactions.objects.filter(
            shop=shop,
            transaction_dt__date=report_date
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
        ws.cell(row=current_row, column=1, value=transaction.transaction_dt.strftime('%Y-%m-%d'))
        ws.cell(row=current_row, column=2, value=transaction.transaction_dt.strftime('%H:%M:%S'))
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
def denomination(request):
    if request.method == 'POST':
        form = DenominationForm(request.POST)
        if form.is_valid():
            # Get form data
            time_period = form.cleaned_data.get('time_period')
            
            # Generate key: DDMMYYYY-XX-Username
            from datetime import datetime
            shop = form.cleaned_data.get('shop')
            print(shop)
            current_date = datetime.now().strftime('%d%m%Y')
            time_period_code = {
                'MORNING': '01',
                'AFTERNOON': '02',
                'EVENING': '03',
                'NIGHT': '04'
            }.get(time_period, '00')
            key = f"{shop.short_name}-{current_date}-{time_period_code}-{request.user.username}"
            
            # Check if key already exists
            if Denomination.objects.filter(key=key).exists():
                messages.error(request, f'Denomination for {time_period.title()} on {datetime.now().strftime("%d-%m-%Y")} already exists!')
                return render(request, 'entries/denomination.html', {'form': form})
            
            
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
                
                log_activity(request, 'CREATE', 'Denomination', key, f'Denomination created: {key}')
                logger.info(f"Denomination added by {request.user.username}")
                messages.success(request, 'Denomination added successfully!')
                transaction_helper.purge_old_denominations()
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
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
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
        'is_admin': is_admin(request.user),
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
    log_activity(request, 'DELETE', 'Denomination', key, f'Denomination deleted: {key}')
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
                
                log_activity(request, 'UPDATE', 'Denomination', key, f'Denomination updated: {key}')
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
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
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
        'created_by': created_by,
        'created_at': created_at,
        'updated_at': updated_at,
        'is_view_mode': True,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin,
    }
    return render(request, 'entries/denomination.html', context)


@login_required
def loan(request):
    """Create a new loan transaction"""
    if request.method != 'POST':
        return redirect('entries:add_entries')

    logger.info("============ Loan Creation Started ============")

    pawn_no    = request.POST.get('pawn_no')
    principal  = request.POST.get('principal')
    interest   = request.POST.get('interest')
    ledger_id  = request.POST.get('ledger')
    loan_type  = request.POST.get('loan_type')
    date_str   = request.POST.get('date')
    time_str   = request.POST.get('time')

    try:
        ledger           = Ledger.objects.get(id=ledger_id)
        principal_amount = Decimal(principal)
        interest_amount  = Decimal(interest)

        # ── Resolve chosen date + time ───────────────────────────────
        try:
            chosen_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localdate()
        except ValueError:
            chosen_date = timezone.localdate()
        try:
            chosen_time = datetime.strptime(time_str, '%H:%M').time() if time_str else timezone.localtime(timezone.now()).time()
        except ValueError:
            chosen_time = timezone.localtime(timezone.now()).time()

        chosen_dt = timezone.make_aware(datetime.combine(chosen_date, chosen_time))

        logger.info(f"Loan -> type=[{loan_type}] | pawn_no=[{pawn_no}] | principal=[{principal_amount}] | interest=[{interest_amount}] | date=[{chosen_date}]")

        # ── Determine labels based on loan type ──────────────────────
        if loan_type == 'LOAN':
            name              = 'Loan'
            principal_tr_type = 'DEBIT'
            principal_remark  = 'Loan Principal'
            interest_remark   = 'Loan Interest'
        else:  # RELEASE
            name              = 'Release'
            principal_tr_type = 'CREDIT'
            principal_remark  = 'Release Principal'
            interest_remark   = 'Release Interest'

        with db_transaction.atomic():
            shop = Shop.objects.select_for_update().get(pk=ledger.shop_id)

            # ── Step 1: Balance check for LOAN type ──────────────────
            if loan_type == 'LOAN':
                available = transaction_helper.get_balance(shop, chosen_date)
                logger.info(f"Balance check -> shop=[{shop.short_name}] | available=[{available}] | required=[{principal_amount}]")
                if principal_amount > available:
                    messages.error(request, f'Insufficient balance in {shop.short_name}. Available: {available}')
                    return redirect('entries:add_entries')

            # ── Step 2: Create loan record ───────────────────────────
            loan_entry = Loan(
                pawn_no=pawn_no,
                shop=shop,
                ledger=ledger,
                type=loan_type,
                principal=principal_amount,
                interest=interest_amount,
                transaction_dt=chosen_dt,
                created_by=request.user,
                updated_by=request.user
            )
            loan_entry.save()
            logger.info(f"Loan record created -> id=[{loan_entry.id}]")

            # ── Step 3: Find existing principal transaction for the day ──
            logger.info(f"Searching transactions -> shop=[{shop.short_name}] | date=[{chosen_date}]")
            existing_principal = Transactions.objects.filter(
                shop=shop,
                remarks=principal_remark,
                transaction_dt__date=chosen_date
            ).first()
            existing_interest = Transactions.objects.filter(
                shop=shop,
                remarks=interest_remark,
                transaction_dt__date=chosen_date
            ).first()
            logger.info(f"Existing principal found: [{existing_principal is not None}] | Existing interest found: [{existing_interest is not None}]")

            # ── Step 4: Update or create principal transaction ───────
            if principal_amount > 0:
                transaction_helper._add_or_create_transaction(
                    trans=existing_principal,
                    amount=principal_amount,
                    remark=principal_remark,
                    name=name,
                    tr_type=principal_tr_type,
                    shop=shop,
                    chosen_dt=chosen_dt,
                    user=request.user,
                    label="principal"
                )
            else:
                logger.info("[principal] amount is 0 — skipping transaction")

            # ── Step 5: Update or create interest transaction ────────
            if interest_amount > 0:
                transaction_helper._add_or_create_transaction(
                    trans=existing_interest,
                    amount=interest_amount,
                    remark=interest_remark,
                    name=name,
                    tr_type='CREDIT',
                    shop=shop,
                    chosen_dt=chosen_dt + timedelta(milliseconds=10),
                    user=request.user,
                    label="interest"
                )
            else:
                logger.info("[interest] amount is 0 — skipping transaction")

        log_activity(request, 'CREATE', 'Loan', loan_entry.id, f'Loan created: {loan_entry.pawn_no}')
        messages.success(request, f'{loan_type.capitalize()} entry created successfully!')
        logger.info(f"Loan [{loan_entry.id}] created by [{request.user.username}]")
        logger.info("============ Loan Creation Completed ============")

    except Ledger.DoesNotExist:
        logger.error(f"Ledger [{ledger_id}] not found")
        messages.error(request, 'Selected ledger does not exist.')
    except Exception as e:
        logger.error(f"Error creating loan: {str(e)}", exc_info=True)
        messages.error(request, f'Error creating loan entry: {str(e)}')

    return redirect('entries:add_entries')


@login_required
@ensure_csrf_cookie
def loans(request):
    """View all loan transactions with pagination and filtering"""
    loans_list = Loan.objects.select_related('ledger', 'created_by', 'updated_by').order_by('-transaction_dt')
    
    # Apply filters
    from_date = (request.GET.get('from_date') or '').strip()
    to_date = (request.GET.get('to_date') or '').strip()
    ledger_filter = (request.GET.get('ledger') or '').strip()
    type_filter = (request.GET.get('type') or '').strip().upper()
    search_query = (request.GET.get('search') or '').strip()

    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            loans_list = loans_list.filter(transaction_dt__date__gte=from_date_obj)
        except ValueError:
            from_date = ''

    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            loans_list = loans_list.filter(transaction_dt__date__lte=to_date_obj)
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
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
        'is_admin_user': is_admin(request.user) or request.user.is_superuser,
    }
    return render(request, 'entries/loans.html', context)


@login_required
def edit_loan(request, pk):
    """Edit a loan transaction"""
    loan = get_object_or_404(Loan, pk=pk)

    # ── Snapshot old values before any changes ──────────────────────
    old_principal    = loan.principal
    old_interest     = loan.interest
    old_type         = loan.type
    old_ledger       = loan.ledger
    old_shop         = old_ledger.shop
    old_date         = timezone.localtime(loan.transaction_dt).date()

    if request.method == 'POST':
        logger.info("============ Loan Update Started ============")
        form = LoanEditForm(request.POST, instance=loan)

        if form.is_valid():
            updated_loan     = form.save(commit=False)
            new_principal    = updated_loan.principal
            new_interest     = updated_loan.interest
            new_type         = updated_loan.type
            new_ledger       = updated_loan.ledger
            new_shop         = new_ledger.shop

            # Resolve new transaction date
            chosen_date = form.cleaned_data.get('date')
            chosen_time = form.cleaned_data.get('time') or timezone.localtime(timezone.now()).time()
            new_dt      = timezone.make_aware(datetime.combine(chosen_date, chosen_time))
            new_date    = chosen_date

            logger.info(f"Old -> type=[{old_type}] | principal=[{old_principal}] | interest=[{old_interest}] | shop=[{old_shop}] | date=[{old_date}]")
            logger.info(f"New -> type=[{new_type}] | principal=[{new_principal}] | interest=[{new_interest}] | shop=[{new_shop}] | date=[{new_date}]")

            # Remark labels
            old_principal_remark = f"{'Loan' if old_type == 'LOAN' else 'Release'} Principal"
            old_interest_remark  = f"{'Loan' if old_type == 'LOAN' else 'Release'} Interest"
            new_principal_remark = f"{'Loan' if new_type == 'LOAN' else 'Release'} Principal"
            new_interest_remark  = f"{'Loan' if new_type == 'LOAN' else 'Release'} Interest"

            same_shop = (old_shop.id == new_shop.id)
            same_date = (old_date == new_date)
            type_changed = (old_type != new_type)

            try:
                with db_transaction.atomic():

                    # ── Step 1: Validate balance for LOAN type ──────────────
                    if new_type == 'LOAN':
                        available = transaction_helper.get_balance(new_shop, new_date)
                        # If same shop and old type was LOAN, add back old principal
                        # because it will be reversed before new amount is applied
                        if same_shop and old_type == 'LOAN':
                            available += old_principal
                        logger.info(f"Balance check -> available=[{available}] | required=[{new_principal}]")
                        if new_principal > available:
                            form.add_error(None, f'Insufficient balance in {new_shop.short_name} on {new_date}. Available: {available}')
                            return render(request, 'entries/edit-loan.html', {
                                'nav_title': 'Loan Transactions',
                                'form': form,
                                'loan': loan,
                            })

                    # ── Step 2: Find old transactions on old date ───────────
                    logger.info(f"Searching old transactions -> shop=[{old_shop.short_name}] | date=[{old_date}]")
                    old_principal_trans = Transactions.objects.filter(
                        shop=old_shop,
                        remarks=old_principal_remark,
                        transaction_dt__date=old_date
                    ).first()
                    old_interest_trans = Transactions.objects.filter(
                        shop=old_shop,
                        remarks=old_interest_remark,
                        transaction_dt__date=old_date
                    ).first()
                    logger.info(f"Old principal trans found: [{old_principal_trans is not None}] | Old interest trans found: [{old_interest_trans is not None}]")

                    # ── Step 3: Find new transactions on new date ───────────
                    logger.info(f"Searching new transactions -> shop=[{new_shop.short_name}] | date=[{new_date}]")
                    new_principal_trans = Transactions.objects.filter(
                        shop=new_shop,
                        remarks=new_principal_remark,
                        transaction_dt__date=new_date
                    ).first()
                    new_interest_trans = Transactions.objects.filter(
                        shop=new_shop,
                        remarks=new_interest_remark,
                        transaction_dt__date=new_date
                    ).first()
                    logger.info(f"New principal trans found: [{new_principal_trans is not None}] | New interest trans found: [{new_interest_trans is not None}]")

                    

                    # ── Step 4: Reduce old amounts from old transactions ─────
                    # Only needed when shop or date changed
                    if not (same_shop and same_date):
                        logger.info("Shop or date changed — reversing old transactions")
                        transaction_helper._reduce_or_delete_transaction(old_principal_trans, old_principal, request.user, label="old principal")
                        transaction_helper._reduce_or_delete_transaction(old_interest_trans,  old_interest,  request.user, label="old interest")

                    # ── Step 5: Apply new amounts to new transactions ────────
                    if same_shop and same_date:
                        logger.info("Same shop & date — checking for type change")

                        if type_changed:
                            # Type changed — delete old transactions and create new ones
                            logger.info(f"Loan type changed [{old_type}] -> [{new_type}] — removing old, creating new")

                            transaction_helper._reduce_or_delete_transaction(old_principal_trans, old_principal, request.user, label="old principal (type change)")
                            transaction_helper._reduce_or_delete_transaction(old_interest_trans,  old_interest,  request.user, label="old interest (type change)")

                            transaction_helper._add_or_create_transaction(
                                trans=new_principal_trans,
                                amount=new_principal,
                                remark=new_principal_remark,
                                name='Loan' if new_type == 'LOAN' else 'Release',
                                tr_type='DEBIT' if new_type == 'LOAN' else 'CREDIT',
                                shop=new_shop,
                                chosen_dt=new_dt,
                                user=request.user,
                                label="new principal (type change)"
                            )
                            transaction_helper._add_or_create_transaction(
                                trans=new_interest_trans,
                                amount=new_interest,
                                remark=new_interest_remark,
                                name='Loan' if new_type == 'LOAN' else 'Release',
                                tr_type='CREDIT',
                                shop=new_shop,
                                chosen_dt=new_dt,
                                user=request.user,
                                label="new interest (type change)"
                            )
                        else:
                            # Same type — just update amounts by delta
                            logger.info("Same type — updating amounts in place")
                            transaction_helper._apply_amount_delta(
                                trans=old_principal_trans,
                                old_amount=old_principal,
                                new_amount=new_principal,
                                remark=new_principal_remark,
                                name='Loan' if new_type == 'LOAN' else 'Release',
                                tr_type='DEBIT' if new_type == 'LOAN' else 'CREDIT',
                                shop=new_shop,
                                chosen_dt=new_dt,
                                user=request.user,
                                label="principal"
                            )
                            transaction_helper._apply_amount_delta(
                                trans=old_interest_trans,
                                old_amount=old_interest,
                                new_amount=new_interest,
                                remark=new_interest_remark,
                                name='Loan' if new_type == 'LOAN' else 'Release',
                                tr_type='CREDIT',
                                shop=new_shop,
                                chosen_dt=new_dt,
                                user=request.user,
                                label="interest"
                            )
                    else:
                        # Different shop or date — add to new transactions
                        logger.info("Different shop or date — applying to new transactions")
                        transaction_helper._add_or_create_transaction(
                            trans=new_principal_trans,
                            amount=new_principal,
                            remark=new_principal_remark,
                            name='Loan' if new_type == 'LOAN' else 'Release',
                            tr_type='DEBIT' if new_type == 'LOAN' else 'CREDIT',
                            shop=new_shop,
                            chosen_dt=new_dt,
                            user=request.user,
                            label="new principal"
                        )
                        transaction_helper._add_or_create_transaction(
                            trans=new_interest_trans,
                            amount=new_interest,
                            remark=new_interest_remark,
                            name='Loan' if new_type == 'LOAN' else 'Release',
                            tr_type='CREDIT',
                            shop=new_shop,
                            chosen_dt=new_dt,
                            user=request.user,
                            label="new interest"
                        )

                    # ── Step 6: Save updated loan ───────────────────────────
                    updated_loan.updated_by = request.user
                    updated_loan.transaction_dt = new_dt
                    updated_loan.save()
                    logger.info(f"Loan [{pk}] saved -> type=[{new_type}] | principal=[{new_principal}] | interest=[{new_interest}]")

                log_activity(request, 'UPDATE', 'Loan', updated_loan.id, f'Loan updated: {updated_loan.pawn_no}')
                messages.success(request, 'Loan transaction updated successfully!')
                logger.info("============ Loan Update Completed ============")
                return redirect('entries:loans')

            except Exception as e:
                logger.error(f"Error updating loan [{pk}]: {str(e)}", exc_info=True)
                messages.error(request, f'An error occurred while updating loan: {str(e)}')

        else:
            messages.error(request, 'Please correct the errors below.')

    else:
        form = LoanEditForm(
            instance=loan,
            initial={
                'date': timezone.localtime(loan.transaction_dt).date(),
                'time': timezone.localtime(loan.transaction_dt).time().replace(second=0, microsecond=0),
            }
        )

    return render(request, 'entries/edit-loan.html', {
        'nav_title': 'Loan Transactions',
        'form': form,
        'loan': loan,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })


@login_required
@csrf_protect
@admin_required
def delete_loan(request, pk):
    """Delete a loan transaction (admin only)"""
    loan = get_object_or_404(Loan, pk=pk)

    if request.method == 'POST':
        loan_id        = loan.id
        loan_pawn_no   = loan.pawn_no
        loan_type      = loan.type
        loan_shop      = loan.ledger.shop
        loan_date      = timezone.localtime(loan.transaction_dt).date()
        loan_principal = loan.principal
        loan_interest  = loan.interest

        principal_remark = f"{'Loan' if loan_type == 'LOAN' else 'Release'} Principal"
        interest_remark  = f"{'Loan' if loan_type == 'LOAN' else 'Release'} Interest"

        logger.info("============ Loan Deletion Started ============")
        logger.info(f"Loan -> id=[{loan_id}] | pawn_no=[{loan_pawn_no}] | type=[{loan_type}] | shop=[{loan_shop.short_name}] | date=[{loan_date}]")
        logger.info(f"Amounts -> principal=[{loan_principal}] | interest=[{loan_interest}]")

        try:
            with db_transaction.atomic():

                # ── Step 1: Find principal and interest transactions ─────
                logger.info(f"Searching transactions -> shop=[{loan_shop.short_name}] | date=[{loan_date}]")
                principal_trans = Transactions.objects.filter(
                    shop=loan_shop,
                    remarks=principal_remark,
                    transaction_dt__date=loan_date
                ).first()
                interest_trans = Transactions.objects.filter(
                    shop=loan_shop,
                    remarks=interest_remark,
                    transaction_dt__date=loan_date
                ).first()
                logger.info(f"Principal trans found: [{principal_trans is not None}] | Interest trans found: [{interest_trans is not None}]")

                # ── Step 2: Reduce or delete principal transaction ───────
                transaction_helper._reduce_or_delete_transaction(
                    trans=principal_trans,
                    amount=loan_principal,
                    user=request.user,
                    label="principal"
                )

                # ── Step 3: Reduce or delete interest transaction ────────
                transaction_helper._reduce_or_delete_transaction(
                    trans=interest_trans,
                    amount=loan_interest,
                    user=request.user,
                    label="interest"
                )

                # ── Step 4: Delete the loan record ───────────────────────
                loan.delete()
                logger.warning(f"Loan deleted by [{request.user.username}] -> id=[{loan_id}] | type=[{loan_type}] | pawn_no=[{loan_pawn_no}]")

            log_activity(request, 'DELETE', 'Loan', loan.id, f'Loan deleted: {loan.pawn_no}')
            messages.success(request, 'Loan transaction deleted successfully!')
            logger.info("============ Loan Deletion Completed ============")

        except Exception as e:
            logger.error(f"Error deleting loan [{loan_id}] by [{request.user.username}]: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting loan.')

        return redirect('entries:loans')

    return render(request, 'entries/delete-loan.html', {
        'nav_title': 'Loan Transactions',
        'loan': loan,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    })


@login_required
@admin_required
def transaction_history(request, pk):
    """Show current transaction and full audit history for a transaction record."""
    transaction = get_object_or_404(
        Transactions.objects.select_related('shop', 'created_by', 'updated_by'),
        pk=pk
    )
    # Exclude creation record to avoid duplication with current record
    history_records = transaction.history.all().order_by('-history_date') 

    context = {
        'nav_title': 'Other Transactions',
        'transaction': transaction,
        'history_records': history_records,
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
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
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'entries/loan_history.html', context)


def custom_404_view(request, exception=None):
    """Custom 404 error handler that properly passes request context"""
    return render(request, '404.html', status=404)


def custom_403_view(request, exception=None):
    """Custom 403 error handler for permission denied"""
    return render(request, '403.html', status=403)

def about(request):
    """About page with system information and credits"""
    context = {
        'nav_title': 'About',
        'is_super_admin': request.user.is_superuser,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'entries/about.html', context)