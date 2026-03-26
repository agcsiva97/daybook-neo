from rest_framework import serializers

from manager.models import Ledger, Shop
from entries.models import Transactions


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ['id', 'short_name', 'name', 'd_no', 'addressline1', 'addressline2', 'place', 'pincode', 'balance']
        read_only_fields = ['id']

class LedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ledger
        fields = ['id', 'name', 'license_number', 'shop']
        read_only_fields = ['id']

class TransactionSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField()
    transaction_dt = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    class Meta:
        model = Transactions
        fields = [
            'id',
            'name',
            'amount',
            'tr_type',
            'shop',
            'created_by',
            'created_at',
            'updated_at',
            'updated_by',
            'transaction_dt',
            'remarks',
        ]