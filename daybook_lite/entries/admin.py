from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Ledger, Transactions, Denomination, Loan, Shop, GLDSLRPriceHistory

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
	list_display = ('name', 'short_name')

@admin.register(Ledger)
class LedgerAdmin(admin.ModelAdmin):
	list_display = ('name', 'license_number', 'shop')


@admin.register(Transactions)
class TransactionsAdmin(SimpleHistoryAdmin):
	list_display = ('amount', 'shop', 'tr_type', 'created_by', 'updated_by', 'created_at', 'updated_at')
	list_filter = ('tr_type', 'shop')
	search_fields = ('shop__name', 'created_by__username', 'updated_by__username')
	history_list_display = ['amount', 'shop', 'tr_type']


@admin.register(Denomination)
class DenominationAdmin(admin.ModelAdmin):
	list_display = ('denomination', 'count', 'amount', 'time_period', 'shop', 'key', 'created_by', 'created_at')
	list_filter = ('denomination', 'time_period', 'shop', 'created_at')
	search_fields = ('denomination', 'key', 'shop__name', 'created_by__username')


@admin.register(Loan)
class LoanAdmin(SimpleHistoryAdmin):
	list_display = ('pawn_no', 'ledger', 'type', 'principal', 'interest', 'created_by', 'created_at', 'updated_at')
	list_filter = ('type', 'ledger', 'created_at')
	search_fields = ('pawn_no', 'ledger__name', 'created_by__username')
	history_list_display = ['pawn_no', 'ledger', 'type', 'principal', 'interest']

@admin.register(GLDSLRPriceHistory)
class GLDSLRPriceHistoryAdmin(admin.ModelAdmin):
	list_display = ('price', 'type', 'updated_at')
	list_filter = ('type', 'updated_at')
	search_fields = ('type',)