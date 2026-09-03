from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'credit_limit', 'active', 'created_at')
    list_filter = ('active',)
    search_fields = ('name', 'phone', 'address')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('name',)
