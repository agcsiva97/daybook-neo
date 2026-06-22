import logging
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages

from ..models import Transactions, Denomination, Loan
from django.db.models.functions import Coalesce
from django.db.models import Case, DecimalField, F, Min, Sum, Value, When, Q
from manager.helper import date_helper, manager_helper
from manager.helper.manager_helper import log_activity
from manager.models import BT_Ledger_Accounts, Shop, Type, Accounts

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Transaction create / update helpers
# ──────────────────────────────────────────────────────────────

def create_transaction(shop, amount, tr_type, remarks, old_balance, chosen_dt, user, account=None,loan_tr_type=None):
    """
    Create a new Transactions record and force its created_at to *chosen_dt*.
    Returns the created transaction instance (with refreshed created_at).
    """

    txn = Transactions.objects.create(
        amount=amount,
        shop=shop,
        tr_type=tr_type,
        remarks=remarks,
        transaction_dt=chosen_dt,
        acc=account,
        created_by=user,
        updated_by=user,
        loan_tr_type=loan_tr_type
    )
    # Force transaction_dt (auto_now_add would override it)
    Transactions.objects.filter(pk=txn.pk).update(transaction_dt=chosen_dt)
    txn.refresh_from_db()
    log_activity(None, 'CREATE', 'Transaction', txn.id, f'Transaction created: {txn.remarks} ({txn.amount} {txn.tr_type}) for {txn.shop.short_name}', shop=shop)
    logger.info(
        f"Created transaction [{txn.id}]: tr_type=[{tr_type}] | "
        f"amount=[{amount}] | loan_tr_type=[{loan_tr_type}]"
    )
    return 1

    
def get_opening_balance(shop, reference_dt=None):
    """
    Get the opening balance for a given shop and reference date.
    This is the new_balance of the most recent transaction before the reference date,
    or the shop's current balance if no such transaction exists.
    """
    if reference_dt is None:
        reference_dt = timezone.localdate()
    transactions = Transactions.objects.filter(
        transaction_dt__date__lt=reference_dt, shop=shop
    ).select_related('shop', 'created_by', 'updated_by')
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
    opening_balance = totals['credit_total'] - totals['debit_total']
    daytransactions = Transactions.objects.filter(
        transaction_dt__date=reference_dt, shop=shop
    ).select_related('created_by', 'updated_by')
    daystotals = daytransactions.aggregate(
        day_total_debit=Coalesce(
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
        day_total_credit=Coalesce(
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
    closing_balance = opening_balance + daystotals['day_total_credit'] - daystotals['day_total_debit']
    print(f"Total debit for shop {shop.short_name} before reference date {reference_dt}: {totals['debit_total']}")
    print(f"Total credit for shop {shop.short_name} before reference date {reference_dt}: {totals['credit_total']}")
    print(f"Calculated opening balance for shop {shop.short_name} on {reference_dt}: {opening_balance}")    
    print(f"Total debit for shop {shop.short_name} on reference date {reference_dt}: {daystotals['day_total_debit']}")
    print(f"Total credit for shop {shop.short_name} on reference date {reference_dt}: {daystotals['day_total_credit']}")
    print(f"Calculated closing balance for shop {shop.short_name} on {reference_dt}: {closing_balance}")
    return {
        'debit_total': round(totals['debit_total'], 2),
        'credit_total': round(totals['credit_total'], 2),
        'opening_balance': round(opening_balance, 2),
        'day_total_debit': round(daystotals['day_total_debit'], 2),
        'day_total_credit': round(daystotals['day_total_credit'], 2),
        'closing_balance': round(closing_balance, 2)
    }

def get_account_balance(account, reference_dt=None):
    if reference_dt is None:
        transactions = Transactions.objects.filter(
            acc=account
        ).select_related('acc', 'created_by', 'updated_by')
    else:
        transactions = Transactions.objects.filter(
            transaction_dt__date__lte=reference_dt, acc=account
        ).select_related('acc', 'created_by', 'updated_by')
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
    return round(totals['credit_total'] - totals['debit_total'], 2)

def get_balance(shop, reference_dt=None):
    if reference_dt is None:
        transactions = Transactions.objects.filter(
            shop=shop
        ).select_related('shop', 'created_by', 'updated_by')
    else:
        transactions = Transactions.objects.filter(
            transaction_dt__date__lte=reference_dt, shop=shop
        ).select_related('shop', 'created_by', 'updated_by')
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
    return round(totals['credit_total'] - totals['debit_total'], 2)

def _reduce_or_delete_transaction(trans, amount, user, label=""):
    """
    Subtract *amount* from an existing transaction.
    If the resulting amount is zero, delete the transaction.
    """
    if trans is None:
        logger.warning(f"[{label}] transaction not found — skipping reduction")
        return

    logger.info(f"[{label}] reducing amount=[{amount}] from trans id=[{trans.id}] current amount=[{trans.amount}]")
    trans.amount -= amount
    trans.updated_by = user

    if trans.amount == 0:
        log_activity(None, 'DELETE', 'Transaction', trans.id, f'Transaction created: {trans.remarks} ({trans.amount} {trans.tr_type}) for {trans.shop.short_name}', shop=trans.shop)
        logger.info(f"[{label}] amount is 0 after reduction — deleting trans id=[{trans.id}]")
        trans.delete()
    else:
        log_activity(None, 'UPDATE', 'Transaction', trans.id, f'Transaction created: {trans.remarks} ({trans.amount} {trans.tr_type}) for {trans.shop.short_name}', shop=trans.shop)
        trans.save()
        logger.info(f"[{label}] updated trans id=[{trans.id}] new amount=[{trans.amount}]")


def _apply_amount_delta(trans, old_amount, new_amount, remark, tr_type, shop, chosen_dt, user, account, loan_tr_type, label=""):
    """
    Same shop + same date: adjust existing transaction by delta (new - old).
    If transaction not found, create a new one with new_amount.
    If resulting amount is zero, delete the transaction.
    """
    delta = new_amount - old_amount
    logger.info(f"[{label}] delta=[{delta}] old=[{old_amount}] new=[{new_amount}]")

    if trans is None:
        logger.info(f"[{label}] no existing transaction — creating new with amount=[{new_amount}]")
        create_transaction(
            shop=shop, amount=new_amount,
            tr_type=tr_type, remarks=remark,
            old_balance=Decimal('0'), chosen_dt=chosen_dt, user=user, account=account,
            loan_tr_type=loan_tr_type
        )
        return

    trans.amount += delta
    trans.updated_by = user

    if trans.amount == 0:
        log_activity(None, 'DELETE', 'Transaction', trans.id, f'Transaction created: {trans.remarks} ({trans.amount} {trans.tr_type}) for {trans.shop.short_name}', shop=trans.shop)
        logger.info(f"[{label}] amount is 0 after delta — deleting trans id=[{trans.id}]")
        trans.delete()
    else:
        log_activity(None, 'UPDATE', 'Transaction', trans.id, f'Transaction created: {trans.remarks} ({trans.amount} {trans.tr_type}) for {trans.shop.short_name}', shop=trans.shop)
        trans.save()
        logger.info(f"[{label}] updated trans id=[{trans.id}] new amount=[{trans.amount}]")


def _add_or_create_transaction(trans, amount, remark, tr_type, shop, chosen_dt, user, account, label="", loan_tr_type=None):
    """
    Different shop or date: add *amount* to existing transaction on new date,
    or create a fresh transaction if none exists.
    """
    if trans is not None:
        logger.info(f"[{label}] existing transaction found id=[{trans.id}] — adding amount=[{amount}]")
        trans.amount += amount
        trans.updated_by = user
        log_activity(None, 'UPDATE', 'Transaction', trans.id, f'Transaction created: {trans.remarks} ({trans.amount} {trans.tr_type}) for {trans.shop.short_name}', shop=trans.shop)
        trans.save()
        logger.info(f"[{label}] updated trans id=[{trans.id}] new amount=[{trans.amount}]")
    else:
        logger.info(f"[{label}] no existing transaction — creating new with amount=[{amount}]")
        create_transaction(
            shop=shop, amount=amount,
            tr_type=tr_type, remarks=remark, loan_tr_type=loan_tr_type,
            old_balance=Decimal('0'), chosen_dt=chosen_dt, user=user, account=account
        )

def purge_old_denominations():
    """
    Delete denomination records older than DEN_PURGE_DAYS days.
    Value is read from Configuration table.
    Falls back to 7 days if config not found.
    """
    logger.info("==== Denomination Purge Started ====")

    try:
        # ── Step 1: Get purge days from config ───────────────────
        from manager.models import Configuration
        purge_days = int(
            Configuration.get_value(
                Configuration.Key.DEN_PURGE_DAYS,
                default='7'
            )
        )
        logger.info(f"Purge config -> DEN_PURGE_DAYS=[{purge_days}]")

        # ── Step 2: Calculate cutoff date ─────────────────────────
        cutoff_date = timezone.localdate() - timedelta(days=purge_days)
        logger.info(f"Purge cutoff date -> [{cutoff_date}]")

        # ── Step 3: Find records to delete ────────────────────────
        old_denominations = Denomination.objects.filter(
            created_at__date__lt=cutoff_date
        )
        count = old_denominations.count()
        logger.info(f"Denominations found for purge -> count=[{count}]")

        if count == 0:
            logger.info("No denominations to purge")
            return 0

        # ── Step 4: Delete records ────────────────────────────────
        old_denominations.delete()
        logger.warning(f"Denomination purge complete -> deleted=[{count}] | cutoff=[{cutoff_date}]")

        logger.info("==== Denomination Purge Completed ====")
        return count

    except ValueError:
        logger.error("DEN_PURGE_DAYS config value is not a valid integer")
        return 0
    except Exception as e:
        logger.error(f"Error during denomination purge: {str(e)}", exc_info=True)
        return 0
    
# ─────────────────────────────────────────
# Account level summary
# ─────────────────────────────────────────

def get_account_summary(account, financial_year: str) -> dict:
    """Returns all balances for an account in a single grouped query."""
    start_date, end_date = date_helper.get_fy_dates(financial_year)
    decimal_mask = Decimal('0.01')
    # Opening: everything before FY — single query
    opening_qs = Transactions.objects.filter(
        acc=account,
        transaction_dt__date__lt=start_date,
    ).aggregate(
        credit=Sum('amount', filter=Q(tr_type='CREDIT')),
        debit=Sum('amount', filter=Q(tr_type='DEBIT')),
    )
    if account.acc_type.group_order == 2:  # For PL accounts, opening balance is considered as zero
        opening = Decimal('0.00')
    else:
        opening = (opening_qs['credit'] or Decimal('0.00')) - (opening_qs['debit'] or Decimal('0.00'))

    # Credits & Debits within FY — single query
    fy_qs = Transactions.objects.filter(
        acc=account,
        transaction_dt__date__gte=start_date,
        transaction_dt__date__lte=end_date,
    ).aggregate(
        credit=Sum('amount', filter=Q(tr_type='CREDIT')),
        debit=Sum('amount', filter=Q(tr_type='DEBIT')),
    )
    credits = fy_qs['credit'] or Decimal('0.00')
    debits  = fy_qs['debit']  or Decimal('0.00')
    closing = opening + credits - debits
    cur_balance = credits - debits
    net_balance = opening + cur_balance
    return {
        'name': account.t_name,
        'opening': Decimal(opening).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'credits': Decimal(credits).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'debits':  Decimal(debits).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'closing': Decimal(closing).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'net_balance': Decimal(net_balance).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'cur_balance': Decimal(cur_balance).quantize(decimal_mask, rounding=ROUND_HALF_UP),
    }

# ─────────────────────────────────────────
# Type level summary
# ─────────────────────────────────────────

def get_type_summary(acc_type, financial_year: str) -> dict:
    """Returns all balances for an account in a single grouped query."""
    start_date, end_date = date_helper.get_fy_dates(financial_year)
    decimal_mask = Decimal('0.01')
    # print(f"Type Summary for {acc_type.e_name} in FY {financial_year}:")
    # print(f"  Start Date: {start_date}, End Date: {end_date}")

    # Opening: everything before FY — single query
    opening_qs = Transactions.objects.filter(
        acc__acc_type=acc_type,
        transaction_dt__date__lt=start_date,
    ).aggregate(
        credit=Sum('amount', filter=Q(tr_type='CREDIT')),
        debit=Sum('amount', filter=Q(tr_type='DEBIT')),
    )
    opening = (opening_qs['credit'] or Decimal('0.00')) - (opening_qs['debit'] or Decimal('0.00'))

    # Credits & Debits within FY — single query
    fy_qs = Transactions.objects.filter(
        acc__acc_type=acc_type,
        transaction_dt__date__gte=start_date,
        transaction_dt__date__lte=end_date,
    ).aggregate(
        credit=Sum('amount', filter=Q(tr_type='CREDIT')),
        debit=Sum('amount', filter=Q(tr_type='DEBIT')),
    )
    credits = fy_qs['credit'] or Decimal('0.00')
    debits  = fy_qs['debit']  or Decimal('0.00')
    # print("credits: ", credits)
    # print("debits: ", debits)
    cur_balance = credits - debits
    # print("cur_balance: ", cur_balance)
    net_balance = opening + cur_balance
    # print("net_balance: ", net_balance)
    closing = opening + credits - debits
    # print("closing: ", closing)
    # print(f"Type Summary for {acc_type.e_name} in FY {financial_year}:")
    # print(f"  Opening: {opening}, Credits: {credits}, Debits: {debits}, Closing: {closing}")
    return {
        'name': acc_type.t_name,
        'opening': Decimal(opening).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'credits': Decimal(credits).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'debits':  Decimal(debits).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'closing': Decimal(closing).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'net_balance': Decimal(net_balance).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'cur_balance': Decimal(cur_balance).quantize(decimal_mask, rounding=ROUND_HALF_UP),
    }

# ─────────────────────────────────────────
# Type level summary
# ─────────────────────────────────────────

def get_group_summary(group, financial_year: str) -> dict:
    """Returns all balances for an account in a single grouped query."""
    start_date, end_date = date_helper.get_fy_dates(financial_year)
    decimal_mask = Decimal('0.01')

    # Opening: everything before FY — single query
    if group[0] == 1:  # For Capital accounts, include PL accounts in the summary
        opening_qs = Transactions.objects.filter(
            acc__acc_type__group_order__in=[1,2],
            transaction_dt__date__lt=start_date,
        ).aggregate(
            credit=Sum('amount', filter=Q(tr_type='CREDIT')),
        debit=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
    else:
        opening_qs = Transactions.objects.filter(
            acc__acc_type__group_order=group[0],
            transaction_dt__date__lt=start_date,
        ).aggregate(
            credit=Sum('amount', filter=Q(tr_type='CREDIT')),
        debit=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
    opening = (opening_qs['credit'] or Decimal('0.00')) - (opening_qs['debit'] or Decimal('0.00'))

    # Credits & Debits within FY — single query
    if group[0] == 1:  # For Capital accounts, include PL accounts in the summary
        fy_qs = Transactions.objects.filter(
            acc__acc_type__group_order__in=[1,2],
            transaction_dt__date__gte=start_date,
            transaction_dt__date__lte=end_date,
        ).aggregate(
            credit=Sum('amount', filter=Q(tr_type='CREDIT')),
            debit=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
    else:
        fy_qs = Transactions.objects.filter(
            acc__acc_type__group_order=group[0],
            transaction_dt__date__gte=start_date,
            transaction_dt__date__lte=end_date,
        ).aggregate(
        credit=Sum('amount', filter=Q(tr_type='CREDIT')),
        debit=Sum('amount', filter=Q(tr_type='DEBIT')),
        )
    credits = fy_qs['credit'] or Decimal('0.00')
    debits  = fy_qs['debit']  or Decimal('0.00')
    if group[0] == 2:  # For PL accounts, opening balance is considered as zero
        opening = Decimal('0.00')
    closing = opening + credits - debits

    return {
        'name': group[2],
        'id': group[0],
        'opening': Decimal(opening).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'credits': Decimal(credits).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'debits':  Decimal(debits).quantize(decimal_mask, rounding=ROUND_HALF_UP),
        'closing': Decimal(closing).quantize(decimal_mask, rounding=ROUND_HALF_UP),
    }

def get_linked_account(ledger, rel_type):
    """
    Returns the Accounts instance linked to the given ledger and rel_type.
    rel_type must be one of: LOAN_PRINCIPAL, LOAN_INTEREST,
                             RELEASE_PRINCIPAL, RELEASE_INTEREST.
    Returns None if no linked account is found.
    """
    try:
        linked = BT_Ledger_Accounts.objects.select_related('account').get(
            ledger=ledger, rel_type=rel_type
        )
        return linked.account
    except BT_Ledger_Accounts.DoesNotExist:
        logger.warning(f"No linked account found for ledger=[{ledger.id}] rel_type=[{rel_type}]")
        return None
    
def group_fy_data(shop, fy):
    groups = manager_helper.get_groups()
    group_fy_data = []
    for group in groups:
        types = Type.objects.filter(shop=shop, group_order=group[0])
        type_entries = []
        for acc_type in types:
            summary = get_type_summary(acc_type, fy)
            accounts = Accounts.objects.filter(shop=shop, acc_type=acc_type)
            acc_entries = []
            type_opening, type_closing = Decimal('0.00'), Decimal('0.00')
            for acc in accounts:
                acc_summary = get_account_summary(acc, fy)
                acc_entries.append({
                    'id':          acc.id,
                    'name':        acc.t_name,
                    'opening':     acc_summary['opening'],
                    'closing':     acc_summary['closing']
                })

                type_opening = type_opening + acc_summary['opening']
                if acc_type.group_order == 2:  # For PL accounts, opening balance is considered as zero
                    type_opening = Decimal('0.00')
                type_closing = type_closing + acc_summary['closing']
            type_entries.append({
                'id':          acc_type.id,
                'name':        acc_type.t_name,
                'opening':     type_opening,
                'closing':     type_closing,
                'accounts':    acc_entries
            })
        group_fy_data.append({
            'id': group[0],
            'name': group[1],
            't_name': group[2],
            'opening': sum([t['opening'] for t in type_entries]),
            'closing': sum([t['closing'] for t in type_entries]),
            'types': type_entries
        })
    return group_fy_data

# ──────────────────────────────────────────────────────────────
# Remark pawn_no management helpers
# ──────────────────────────────────────────────────────────────

def _parse_pawn_nos(remark: str) -> tuple[str, list[str]]:
    """
    Split a remark into base text and list of pawn nos.
    Example:
        "Loan Principal [A1511, C563]" -> ("Loan Principal", ["A1511", "C563"])
        "Loan Principal"               -> ("Loan Principal", [])
    """
    import re
    match = re.search(r'\[([^\]]*)\]$', remark.strip())
    if match:
        base = remark[:match.start()].strip()
        pawn_nos = [p.strip() for p in match.group(1).split(',') if p.strip()]
    else:
        base = remark.strip()
        pawn_nos = []
    return base, pawn_nos


def _build_remark(base: str, pawn_nos: list[str]) -> str:
    """
    Reconstruct remark string from base and pawn no list.
    Example:
        ("Loan Principal", ["A1511", "C563"]) -> "Loan Principal [A1511, C563]"
        ("Loan Principal", [])                -> "Loan Principal"
    """
    if pawn_nos:
        return f"{base} [{', '.join(pawn_nos)}]"
    return base


def append_pawn_no_to_remark(trans, pawn_no: str, user, label=""):
    """
    Add pawn_no to the transaction's remark list if not already present.
    Saves the transaction.
    """
    if trans is None:
        logger.warning(f"[{label}] transaction not found — cannot append pawn_no=[{pawn_no}]")
        return

    base, pawn_nos = _parse_pawn_nos(trans.remarks)
    if pawn_no not in pawn_nos:
        pawn_nos.append(pawn_no)
        trans.remarks = _build_remark(base, pawn_nos)
        trans.updated_by = user
        trans.save()
        logger.info(f"[{label}] appended pawn_no=[{pawn_no}] to trans id=[{trans.id}] remarks=[{trans.remarks}]")
    else:
        logger.info(f"[{label}] pawn_no=[{pawn_no}] already in trans id=[{trans.id}] remarks — skipping")


def remove_pawn_no_from_remark(trans, pawn_no: str, user, label=""):
    if trans is None:
        logger.warning(f"[{label}] transaction not found — cannot remove pawn_no=[{pawn_no}]")
        return

    base, pawn_nos = _parse_pawn_nos(trans.remarks)
    if pawn_no in pawn_nos:
        pawn_nos.remove(pawn_no)
        if len(pawn_nos) == 0:
            trans.remarks = base
        elif len(pawn_nos) == 1:
            trans.remarks = f"{base} [{pawn_nos[0]}]" if base else f"[{pawn_nos[0]}]"
        else:
            trans.remarks = f"{base} [{pawn_nos[0]} - {pawn_nos[-1]}]" if base else f"[{pawn_nos[0]} - {pawn_nos[-1]}]"
        trans.updated_by = user
        trans.save()
        logger.info(f"[{label}] removed pawn_no=[{pawn_no}] remarks=[{trans.remarks}]")
    else:
        logger.info(f"[{label}] pawn_no=[{pawn_no}] not found in trans id=[{trans.id}] — skipping")

def is_loan_transaction(remark: str) -> bool:
    """
    Determine if a transaction remark indicates a loan-related transaction.
    This is a simple heuristic based on the presence of certain keywords.
    """
    loan_keywords = ['lp', 'li', 'rp', 'ri']
    remark_lower = remark.lower()
    return any(keyword in remark_lower for keyword in loan_keywords)

def append_pawn_no_range_to_remark(trans, pawn_no: str, user, label=""):
    """
    Add pawn_no to the transaction's remark list.
    Remark stores first and last pawn_no as a range: [A100 - A200]
    If only one pawn_no exists, stored as: [A100]
    """
    if trans is None:
        logger.warning(f"[{label}] transaction not found — cannot append pawn_no=[{pawn_no}]")
        return

    base, pawn_nos = _parse_pawn_nos(trans.remarks)
    if pawn_no not in pawn_nos:
        pawn_nos.append(pawn_no)

    # Store only first and last
    if len(pawn_nos) == 1:
        range_str = pawn_nos[0]
    else:
        range_str = f"{pawn_nos[0]} - {pawn_nos[-1]}"

    trans.remarks = f"{base} [{range_str}]" if base else f"[{range_str}]"
    trans.updated_by = user
    trans.save()
    logger.info(f"[{label}] updated remarks=[{trans.remarks}] for trans id=[{trans.id}]")