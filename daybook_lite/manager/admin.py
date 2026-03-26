from django.contrib import admin

from .models import Configuration, ActivityLog

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