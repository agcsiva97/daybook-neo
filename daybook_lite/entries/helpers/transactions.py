import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages

from ..models import Transactions, Denomination, Loan, Shop
from django.db.models.functions import Coalesce
from django.db.models import Case, DecimalField, F, Min, Sum, Value, When

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Balance lookup helpers
# ──────────────────────────────────────────────────────────────

def get_previous_balance(shop, reference_dt):
    """
    Get the new_balance of the most recent transaction for *shop*
    that was created strictly before *reference_dt*.
    Falls back to shop.balance if no earlier transaction exists.
    This is used as old_balance when inserting a transaction at an older date.
    """
    prev_transaction = (
        Transactions.objects
        .filter(shop=shop, created_at__lt=reference_dt)
        .order_by('-created_at')
        .first()
    )
    if prev_transaction and prev_transaction.new_balance is not None:
        logger.info(
            f"Previous transaction found for {shop.name} before {reference_dt}: "
            f"new_balance=[{prev_transaction.new_balance}]"
        )
        return prev_transaction.new_balance
    # No earlier transaction – use the shop's current balance
    logger.info(f"No previous transaction for {shop.name} before {reference_dt}, using shop balance [{shop.balance}]")
    return shop.balance


def calculate_new_balance(old_balance, amount, tr_type):
    """
    Calculate new_balance given old_balance, amount and transaction type.
    DEBIT subtracts; CREDIT adds.
    """
    if tr_type.upper() == 'DEBIT':
        return old_balance - amount
    return old_balance + amount


# ──────────────────────────────────────────────────────────────
# Transaction create / update helpers
# ──────────────────────────────────────────────────────────────

def create_transaction(shop, amount, name, tr_type, remarks, old_balance, chosen_dt, user):
    """
    Create a new Transactions record and force its created_at to *chosen_dt*.
    Returns the created transaction instance (with refreshed created_at).
    """
    new_balance = calculate_new_balance(old_balance, amount, tr_type)
    txn = Transactions.objects.create(
        amount=amount,
        name=name,
        shop=shop,
        tr_type=tr_type,
        remarks=remarks,
        old_balance=old_balance,
        new_balance=new_balance,
        transaction_dt=chosen_dt,
        created_by=user,
        updated_by=user,
    )
    # Force transaction_dt (auto_now_add would override it)
    Transactions.objects.filter(pk=txn.pk).update(transaction_dt=chosen_dt)
    txn.refresh_from_db()
    logger.info(
        f"Created transaction [{txn.id}]: name=[{name}] | tr_type=[{tr_type}] | "
        f"amount=[{amount}] | old_bal=[{old_balance}] | new_bal=[{new_balance}]"
    )
    return 1


def update_transaction_amount(txn, additional_amount, tr_type, user, new_old_balance=None):
    """
    Add *additional_amount* to an existing transaction and recalculate its
    new_balance.  Optionally update old_balance when it has shifted (e.g. the
    preceding principal changed).
    Returns the updated transaction.
    """
    logger.info(
        f"Before update [{txn.id}]: amount=[{txn.amount}] | old_bal=[{txn.old_balance}] | new_bal=[{txn.new_balance}]"
    )
    txn.amount += additional_amount
    if new_old_balance is not None:
        txn.old_balance = new_old_balance
    txn.new_balance = calculate_new_balance(txn.old_balance, txn.amount, tr_type)
    txn.updated_by = user
    txn.save()
    logger.info(
        f"After update  [{txn.id}]: amount=[{txn.amount}] | old_bal=[{txn.old_balance}] | new_bal=[{txn.new_balance}]"
    )
    return txn


# ──────────────────────────────────────────────────────────────
# Cascade / subsequent-balance helpers
# ──────────────────────────────────────────────────────────────

def update_latest_transactions(request, transaction, new_balance, shop_id=None):
    """
    Recalculate old_balance / new_balance for every transaction in *shop*
    that was created **after** *transaction.created_at*, cascading the running
    balance forward.
    Returns 1 on success, 0 on error. The final cascaded balance is stored
    on the transaction object as transaction._cascaded_balance for the caller
    to use if needed.
    """
    try:
        if shop_id is None:
            shop_id = transaction.shop_id
        latest_transactions = (
            Transactions.objects
            .filter(created_at__gt=transaction.created_at, shop_id=shop_id)
            .order_by('created_at')
        )
        if latest_transactions.exists():
            for trans in latest_transactions:
                logger.info(
                    f"Before cascade: [{trans.id}] NAME:[{trans.name}] | AMOUNT:[{trans.amount}] | "
                    f"TR_TYPE:[{trans.tr_type}] | OLD_BAL:[{trans.old_balance}] | NEW_BAL:[{trans.new_balance}]"
                )
                trans.old_balance = new_balance
                trans.new_balance = calculate_new_balance(new_balance, trans.amount, trans.tr_type)
                new_balance = trans.new_balance
                trans.save()
                logger.info(
                    f"After cascade:  [{trans.id}] NAME:[{trans.name}] | AMOUNT:[{trans.amount}] | "
                    f"TR_TYPE:[{trans.tr_type}] | OLD_BAL:[{trans.old_balance}] | NEW_BAL:[{trans.new_balance}]"
                )
            logger.info(f"{latest_transactions.count()} subsequent transactions updated. Final balance=[{new_balance}]")
        else:
            logger.info("No subsequent transactions found to cascade.")

        # Store the final cascaded balance so the caller can update the ledger
        transaction._cascaded_balance = new_balance
        return 1
    except Exception as e:
        logger.error(f"Error updating latest transactions: {str(e)}", exc_info=True)
        messages.error(request, f'Error updating latest transactions: {str(e)}')
        return 0


# ──────────────────────────────────────────────────────────────
# Legacy reversal helpers (kept for edit_loan compatibility)
# ──────────────────────────────────────────────────────────────

def reverse_principal_transactions(request, old_principal_trans, old_principal, type):
    """Reverse (subtract) a principal amount from an existing transaction."""
    try:
        old_principal_trans.amount = old_principal_trans.amount - old_principal
        if type == 'LOAN':
            old_principal_trans.new_balance = old_principal_trans.new_balance + old_principal
        else:
            old_principal_trans.new_balance = old_principal_trans.new_balance - old_principal
        old_principal_trans.updated_by = request.user
        old_principal_trans.save()
        return 1
    except Exception as e:
        logger.error(f"Error reversing principal transaction: {str(e)}", exc_info=True)
        messages.error(request, f'Error reversing principal transaction: {str(e)}')
        return 0


def reverse_interest_transactions(request, old_interest_trans, old_interest):
    """Reverse (subtract) an interest amount from an existing transaction."""
    try:
        old_interest_trans.amount = old_interest_trans.amount - old_interest
        old_interest_trans.new_balance = old_interest_trans.new_balance - old_interest
        old_interest_trans.updated_by = request.user
        old_interest_trans.save()
        return 1
    except Exception as e:
        logger.error(f"Error reversing interest transaction: {str(e)}", exc_info=True)
        messages.error(request, f'Error reversing interest transaction: {str(e)}')
        return 0
    
def get_opening_balance(shop, reference_dt):
    """
    Get the opening balance for a given shop and reference date.
    This is the new_balance of the most recent transaction before the reference date,
    or the shop's current balance if no such transaction exists.
    """
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
        logger.info(f"[{label}] amount is 0 after reduction — deleting trans id=[{trans.id}]")
        trans.delete()
    else:
        trans.save()
        logger.info(f"[{label}] updated trans id=[{trans.id}] new amount=[{trans.amount}]")


def _apply_amount_delta(trans, old_amount, new_amount, remark, name, tr_type, shop, chosen_dt, user, label=""):
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
            shop=shop, amount=new_amount, name=name,
            tr_type=tr_type, remarks=remark,
            old_balance=Decimal('0'), chosen_dt=chosen_dt, user=user
        )
        return

    trans.amount += delta
    trans.updated_by = user

    if trans.amount == 0:
        logger.info(f"[{label}] amount is 0 after delta — deleting trans id=[{trans.id}]")
        trans.delete()
    else:
        trans.save()
        logger.info(f"[{label}] updated trans id=[{trans.id}] new amount=[{trans.amount}]")


def _add_or_create_transaction(trans, amount, remark, name, tr_type, shop, chosen_dt, user, label=""):
    """
    Different shop or date: add *amount* to existing transaction on new date,
    or create a fresh transaction if none exists.
    """
    if trans is not None:
        logger.info(f"[{label}] existing transaction found id=[{trans.id}] — adding amount=[{amount}]")
        trans.amount += amount
        trans.updated_by = user
        trans.save()
        logger.info(f"[{label}] updated trans id=[{trans.id}] new amount=[{trans.amount}]")
    else:
        logger.info(f"[{label}] no existing transaction — creating new with amount=[{amount}]")
        create_transaction(
            shop=shop, amount=amount, name=name,
            tr_type=tr_type, remarks=remark,
            old_balance=Decimal('0'), chosen_dt=chosen_dt, user=user
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