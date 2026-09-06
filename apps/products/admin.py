from django.contrib import admin
from django.utils.html import format_html

from apps.inventory.services import inventory_service

from .models import Product, ProductCategory


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'active')
    search_fields = ('name', 'code')
    ordering = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('thumbnail', 'name', 'code', 'category', 'unit', 'sale_price', 'current_stock', 'active', 'updated_at')
    list_filter = ('category', 'unit', 'active')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at', 'image_preview')
    ordering = ('name',)
    fields = (
        'name', 'code', 'category', 'unit', 'sale_price',
        'image', 'image_preview', 'active', 'description',
        'created_at', 'updated_at',
    )

    @admin.display(description="Ombor qoldig'i")
    def current_stock(self, obj):
        return f'{inventory_service.get_stock(obj)} {obj.unit}'

    @admin.display(description='Rasm')
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:36px;height:36px;object-fit:cover;border-radius:4px;">', obj.image.url)
        return '—'

    @admin.display(description='Rasm')
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width:200px;max-height:200px;object-fit:cover;border-radius:6px;">', obj.image.url)
        return "Rasm yuklanmagan"
