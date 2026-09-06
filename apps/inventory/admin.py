from django.contrib import admin

from .models import InventoryCount, InventoryCountItem, StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'direction', 'quantity', 'pieces', 'movement_type', 'unit_cost', 'date', 'reference')
    list_filter = ('direction', 'movement_type', 'date')
    search_fields = ('product__name', 'product__code', 'reference')
    autocomplete_fields = ('product', 'created_by')
    readonly_fields = ('created_at',)
    date_hierarchy = 'date'
    ordering = ('-date', '-id')


class InventoryCountItemInline(admin.TabularInline):
    model = InventoryCountItem
    extra = 0
    readonly_fields = ('system_kg', 'system_pieces', 'diff_kg', 'diff_pieces')


@admin.register(InventoryCount)
class InventoryCountAdmin(admin.ModelAdmin):
    list_display = ('pk', 'date', 'status', 'created_by')
    list_filter = ('status', 'date')
    inlines = [InventoryCountItemInline]
    readonly_fields = ('created_at', 'updated_at')
