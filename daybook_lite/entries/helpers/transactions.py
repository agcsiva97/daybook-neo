import logging
from decimal import Decimal

from django.contrib import messages

from ..models import Transactions, Denomination, Loan, Shop

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
        created_at=chosen_dt,
        created_by=user,
        updated_by=user,
    )
    # Force created_at (auto_now_add would override it)
    Transactions.objects.filter(pk=txn.pk).update(created_at=chosen_dt)
    txn.refresh_from_db()
    logger.info(
        f"Created transaction [{txn.id}]: name=[{name}] | tr_type=[{tr_type}] | "
        f"amount=[{amount}] | old_bal=[{old_balance}] | new_bal=[{new_balance}]"
    )
    return txn


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
    