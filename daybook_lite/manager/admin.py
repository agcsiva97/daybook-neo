from django.contrib import admin

from .models import BT_Ledger_Accounts, Configuration, ActivityLog, Type, Accounts

# Register your models here.
@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display  = ['group', 'key', 'value']
    list_filter   = ['group']
    search_fields = ['key', 'value']
    ordering      = ['group', 'key']
    list_editable = ['value']   # ← edit value directly from list view

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display   = ['created_at', 'user', 'action', 'model_name', 'object_id', 'description', 'ip_address']
    list_filter    = ['action', 'model_name', 'created_at']
    search_fields  = ['user__username', 'description', 'object_id', 'model_name']
    ordering       = ['-created_at']
    readonly_fields = ['user', 'action', 'model_name', 'object_id', 'description', 'ip_address', 'created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False       # ← prevent manual creation

    def has_change_permission(self, request, obj=None):
        return False       # ← prevent editing

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser   # ← only superuser can delete
    
@admin.register(BT_Ledger_Accounts)
class BT_Ledger_AccountsAdmin(admin.ModelAdmin):
    list_display = ['account', 'rel_type', 'ledger']
    search_fields = ['account__e_name', 'account__t_name', 'rel_type', 'ledger__name']
    ordering = ['account__e_name']

@admin.register(Type)
class TypeAdmin(admin.ModelAdmin):
    list_display = ['e_name', 't_name','shop__name']
    search_fields = ['e_name', 't_name']
    ordering = ['e_name']

@admin.register(Accounts)
class AccountsAdmin(admin.ModelAdmin):
    list_display = ['e_name', 't_name', 'acc_type','shop__name']
    search_fields = ['e_name', 't_name', 'acc_type__e_name', 'acc_type__t_name']
    ordering = ['e_name']