from datetime import datetime, timedelta, date as date_type
from os import name
import logging

from django.contrib.auth.decorators import login_required, user_passes_test


def _is_admin(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists()
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.utils.timezone import get_current_timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from entries.models import Ledger, Loan, Transactions, Shop
from django.db.models import Sum

from .serializers import LedgerSerializer, ShopSerializer, TransactionSerializer
from django.db import transaction as db_transaction
from manager.models import Configuration
from entries.helpers import transactions as transaction_helper
from manager.helper.manager_helper import log_activity

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Configuration API endpoints
# ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@login_required
def get_session_timeout(request):
    """Get session timeout in seconds from database configuration."""
    try:
        timeout_str = Configuration.get_value('SESSION_TIMEOUT', '1800')
        timeout_seconds = int(timeout_str)
    except (ValueError, TypeError):
        from django.conf import settings
        timeout_seconds = getattr(settings, 'SESSION_COOKIE_AGE', 1800)
    
    return JsonResponse({'timeout_seconds': timeout_seconds})


# ──────────────────────────────────────────────────────────────
# Shop CRUD API endpoints
# ──────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def shop_list_create(request):
    """
    GET  - List all shops
    POST - Create a new shop (id provided by the user)
    """
    if request.method == 'GET':
        short_name = request.GET.get('short_name', '').strip()
        name = request.GET.get('name', '').strip()
        
        logger.info(f"Shop list API called with filters: short_name='{short_name}', name='{name}'")
        
        shops = Shop.objects.all().order_by('name')
        
        # Apply filters only if parameters are provided and not empty
        if short_name:
            shops = shops.filter(short_name__icontains=short_name)
            logger.info(f"Applied short_name filter: '{short_name}'")
        if name:
            shops = shops.filter(name__icontains=name)
            logger.info(f"Applied name filter: '{name}'")
            
        shop_count = shops.count()
        logger.info(f"Returning {shop_count} shops")
            
        serializer = ShopSerializer(shops, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = ShopSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
def shop_detail(request, pk):
    """
    GET    - Retrieve a single shop
    PUT    - Update a shop
    DELETE - Delete a shop
    """
    try:
        shop = Shop.objects.get(pk=pk)
    except Shop.DoesNotExist:
        return Response({'error': 'Shop not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = ShopSerializer(shop, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        shop.delete()
        return Response({'message': 'Shop deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


@login_required
def shop_ledgers(request, pk):
    """Return ledgers belonging to a shop as JSON."""
    ledgers = Ledger.objects.filter(shop_id=pk).order_by('name')
    data = [{'id': l.pk, 'name': l.name} for l in ledgers]
    return JsonResponse(data, safe=False)

@api_view(['GET', 'POST'])
def shop_ledger_list_create(request, pk):
    """
    GET  - List all ledgers for a shop
    POST - Create a new ledger for a shop
    """
    try:
        shop = Shop.objects.get(pk=pk)
    except Shop.DoesNotExist:
        return Response({'error': 'Shop not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        logger.info(f"Fetching ledgers for shop ID: {shop.id}, Name: {shop.short_name}")
        ledgers = Ledger.objects.filter(shop_id=pk).order_by('name')
        logger.info(f"Found {ledgers.count()} ledgers for shop ID {shop.id} - {shop.short_name}")

        serializer = LedgerSerializer(ledgers, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        # Add shop_id to the data before validation
        data = request.data.copy()
        data['shop'] = pk

        serializer = LedgerSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@login_required
@user_passes_test(_is_admin, login_url='/accounts/login/')
def transaction_pie_data(request):
    """Returns debit/credit transaction totals grouped by name as JSON.
    Query params: from_date, to_date (YYYY-MM-DD), shop (ID, optional).
    Defaults to last 7 days.
    """
    start_date, end_date = _parse_date_range(request)
    shop_id = _parse_shop_id(request)

    from django.db.models import Sum

    def build_pie(tr_type):
        qs = Transactions.objects.filter(
            tr_type=tr_type,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        ).exclude(name='Openning Deposit')
        if shop_id:
            qs = qs.filter(shop_id=shop_id)
        qs = qs.values('name').annotate(total=Sum('amount')).order_by('-total')
        labels = []
        values = []
        for item in qs:
            label = item['name'].strip() if item['name'] and item['name'].strip() else 'Unnamed'
            labels.append(label)
            values.append(float(item['total']))
        return labels, values

    debit_labels, debit_values   = build_pie('DEBIT')
    credit_labels, credit_values = build_pie('CREDIT')

    return JsonResponse({
        'debit':  { 'labels': debit_labels,  'values': debit_values },
        'credit': { 'labels': credit_labels, 'values': credit_values },
        'range': { 'from_date': str(start_date), 'to_date': str(end_date) },
    })


def _parse_date_range(request):
    """Helper: parse from_date / to_date query params. Returns (start_date, end_date)."""
    today = timezone.localdate()
    from_date_str = request.GET.get('from_date', '')
    to_date_str   = request.GET.get('to_date', '')
    try:
        start_date = date_type.fromisoformat(from_date_str) if from_date_str else today - timedelta(days=6)
    except ValueError:
        start_date = today - timedelta(days=6)
    try:
        end_date = date_type.fromisoformat(to_date_str) if to_date_str else today
    except ValueError:
        end_date = today
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date


def _parse_shop_id(request):
    """Helper: parse optional shop query param. Returns int or None."""
    shop_str = request.GET.get('shop', '')
    if shop_str:
        try:
            return int(shop_str)
        except (ValueError, TypeError):
            pass
    return None


@login_required
@user_passes_test(_is_admin, login_url='/accounts/login/')
def dashboard_chart_data(request):
    """Returns loan/release counts for a date range as JSON.
    Query params: from_date, to_date (YYYY-MM-DD), shop (ID, optional).
    Defaults to last 7 days.
    """
    today = timezone.localdate()
    start_date, end_date = _parse_date_range(request)
    shop_id = _parse_shop_id(request)

    date_range = []
    d = start_date
    while d <= end_date:
        date_range.append(d)
        d += timedelta(days=1)

    labels = [d.strftime('%Y-%m-%d') for d in date_range]

    tz = get_current_timezone()

    loan_base = Loan.objects.filter(type='LOAN', created_at__date__gte=start_date, created_at__date__lte=end_date)
    release_base = Loan.objects.filter(type='RELEASE', created_at__date__gte=start_date, created_at__date__lte=end_date)
    if shop_id:
        loan_base = loan_base.filter(shop_id=shop_id)
        release_base = release_base.filter(shop_id=shop_id)

    loan_counts_qs = (
        loan_base
        .annotate(day=TruncDate('created_at', tzinfo=tz))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    loan_map = {item['day'].strftime('%Y-%m-%d'): item['count'] for item in loan_counts_qs}

    release_counts_qs = (
        release_base
        .annotate(day=TruncDate('created_at', tzinfo=tz))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    release_map = {item['day'].strftime('%Y-%m-%d'): item['count'] for item in release_counts_qs}

    loan_data    = [loan_map.get(str(d), 0)    for d in date_range]
    release_data = [release_map.get(str(d), 0) for d in date_range]

    # Summary: total debit/credit for the range (also filtered by shop if set)
    debit_base  = Transactions.objects.filter(tr_type='DEBIT',  created_at__date__gte=start_date, created_at__date__lte=end_date)
    credit_base = Transactions.objects.filter(tr_type='CREDIT', created_at__date__gte=start_date, created_at__date__lte=end_date).exclude(name='Openning Deposit')
    if shop_id:
        debit_base  = debit_base.filter(shop_id=shop_id)
        credit_base = credit_base.filter(shop_id=shop_id)
    total_debit  = float(debit_base.aggregate(total=Sum('amount'))['total'] or 0)
    total_credit = float(credit_base.aggregate(total=Sum('amount'))['total'] or 0)

    return JsonResponse({
        'labels': labels,
        'loan_data': loan_data,
        'release_data': release_data,
        'summary': {
            'total_debit':     total_debit,
            'total_credit':    total_credit,
            'loans_week':   sum(loan_data),
            'releases_week': sum(release_data),
        },
        'range': {
            'from_date': str(start_date),
            'to_date':   str(end_date),
        },
    })

@api_view(['POST'])
def create_transaction(request):
    serializer = TransactionSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning(f"Transaction API invalid -> errors={serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        with db_transaction.atomic():

            # ── Prepare transaction object ─────────────────────
            transaction_obj = Transactions(**data)

            if request.user.is_authenticated:
                transaction_obj.created_by = request.user
                transaction_obj.updated_by = request.user

            # ── Date + Time handling ───────────────────────────
            chosen_date = data.get('date')
            chosen_time = data.get('time') or timezone.localtime(timezone.now()).time()

            transaction_obj.transaction_dt = timezone.make_aware(
                datetime.combine(chosen_date, chosen_time)
            )

            logger.info("============ Transaction API Creation Started ============")
            logger.info(
                f"Transaction -> type=[{transaction_obj.tr_type}] | amount=[{transaction_obj.amount}] | date=[{transaction_obj.transaction_dt}]"
            )

            # ── Lock shop row ──────────────────────────────────
            shop = Shop.objects.select_for_update().get(pk=transaction_obj.shop_id)

            logger.info(f"Shop -> name=[{shop.short_name}]")

            # ── Balance check ──────────────────────────────────
            if transaction_obj.tr_type == 'DEBIT':
                available = transaction_helper.get_balance(shop, chosen_date)

                logger.info(
                    f"Balance check -> available=[{available}] | required=[{transaction_obj.amount}]"
                )

                if transaction_obj.amount > available:
                    return Response(
                        {
                            "error": f"Insufficient balance in {shop.short_name}",
                            "available": available
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # ── Save transaction ───────────────────────────────
            transaction_obj.save()

            logger.info(
                f"Transaction [{transaction_obj.id}] created -> type=[{transaction_obj.tr_type}] | amount=[{transaction_obj.amount}] | shop=[{shop.short_name}]"
            )

        # ── Activity log (outside atomic is also fine) ─────────
        log_activity(
            request,
            'CREATE',
            'Transaction',
            transaction_obj.id,
            f'Transaction created: {transaction_obj.name} ({transaction_obj.amount} {transaction_obj.tr_type}) for {shop.short_name}'
        )

        logger.info("============ Transaction API Creation Completed ============")

        return Response(
            {
                "message": "Transaction created successfully",
                "id": transaction_obj.id
            },
            status=status.HTTP_201_CREATED
        )

    except Shop.DoesNotExist:
        return Response(
            {"error": "Invalid shop"},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        logger.error(
            f"Error creating transaction via API by [{request.user}]: {str(e)}",
            exc_info=True
        )

        return Response(
            {"error": "Something went wrong"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])    
def get_transactions(request):
    """Returns transactions as JSON. Supports optional ?shop=ID filter."""
    if request.method == 'GET':
        print('get_transactions called')
        transactions_list = Transactions.objects.all().order_by('transaction_dt')

        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        shop_filter = request.GET.get('shop')
        type_filter = request.GET.get('type')
        search_query = request.GET.get('search', '')
        name_search_query = request.GET.get('name_search', '')   

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

        serializer = TransactionSerializer(transactions_list, many=True)
        return Response(serializer.data)

@api_view(['GET'])    
def get_shop_transactions(request,pk=None):
    """Returns transactions as JSON. Supports optional ?shop=ID filter."""
    if request.method == 'GET':
        print('get_shop_transactions called with pk:', pk)
        transactions_list = Transactions.objects.filter(shop_id=pk).order_by('transaction_dt')

        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        shop_filter = request.GET.get('shop')
        type_filter = request.GET.get('type')
        search_query = request.GET.get('search', '')
        name_search_query = request.GET.get('name_search', '')   

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

        serializer = TransactionSerializer(transactions_list, many=True)
        return Response(serializer.data)