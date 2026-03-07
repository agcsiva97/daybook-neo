from rest_framework import serializers

from entries.models import Shop


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ['id', 'short_name', 'name', 'd_no', 'addressline1', 'addressline2', 'place', 'pincode', 'balance']
        read_only_fields = ['id', 'short_name']
