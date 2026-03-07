from datetime import timedelta, date as date_type

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

from .serializers import ShopSerializer


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
        shops = Shop.objects.all().order_by('name')
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
        )
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
    credit_base = Transactions.objects.filter(tr_type='CREDIT', created_at__date__gte=start_date, created_at__date__lte=end_date)
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
