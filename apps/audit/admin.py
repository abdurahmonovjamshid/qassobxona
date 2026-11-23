from django.contrib import admin

try:  # Mezon — Unfold admin
    from unfold.admin import ModelAdmin
except ImportError:  # Qassobxona — oddiy admin
    from django.contrib.admin import ModelAdmin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = ('created_at', 'user', 'source', 'action', 'content_type', 'object_repr')
    list_filter = ('action', 'source', 'content_type', 'created_at')
    search_fields = ('object_repr', 'user__username', 'user__first_name')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
