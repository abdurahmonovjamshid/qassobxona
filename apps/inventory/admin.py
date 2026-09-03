from django.contrib import admin

from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'direction', 'quantity', 'movement_type', 'unit_cost', 'date', 'reference')
    list_filter = ('direction', 'movement_type', 'date')
    search_fields = ('product__name', 'product__code', 'reference')
    autocomplete_fields = ('product', 'created_by')
    readonly_fields = ('created_at',)
    date_hierarchy = 'date'
    ordering = ('-date', '-id')
