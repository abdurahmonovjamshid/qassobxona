from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Sale, SaleItem
from .services import sale_service


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    autocomplete_fields = ('product',)
    readonly_fields = ('total', 'cost_price', 'profit')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_number', 'customer', 'date', 'total_amount', 'paid_amount', 'debt_amount', 'status')
    list_filter = ('status', 'date')
    search_fields = ('sale_number', 'customer__name', 'customer__phone')
    autocomplete_fields = ('customer', 'created_by')
    readonly_fields = ('total_amount', 'debt_amount', 'status', 'created_at', 'updated_at')
    date_hierarchy = 'date'
    ordering = ('-date', '-id')
    inlines = (SaleItemInline,)
    actions = ('confirm_sales', 'cancel_sales')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="✅ Tanlangan sotuvlarni tasdiqlash (ombordan chiqim qiladi)")
    def confirm_sales(self, request, queryset):
        ok, failed = 0, 0
        for sale in queryset:
            try:
                sale_service.confirm_sale(sale, user=request.user)
                ok += 1
            except ValidationError as exc:
                failed += 1
                self.message_user(request, f'{sale}: {"; ".join(exc.messages)}', level=messages.ERROR)
        if ok:
            self.message_user(request, f'{ok} ta sotuv tasdiqlandi.', level=messages.SUCCESS)
        if failed:
            self.message_user(request, f'{failed} tasida xatolik yuz berdi.', level=messages.WARNING)

    @admin.action(description="❌ Tanlangan sotuvlarni bekor qilish")
    def cancel_sales(self, request, queryset):
        ok, failed = 0, 0
        for sale in queryset:
            try:
                sale_service.cancel_sale(sale, user=request.user)
                ok += 1
            except ValidationError as exc:
                failed += 1
                self.message_user(request, f'{sale}: {"; ".join(exc.messages)}', level=messages.ERROR)
        if ok:
            self.message_user(request, f'{ok} ta sotuv bekor qilindi.', level=messages.SUCCESS)
        if failed:
            self.message_user(request, f'{failed} tasida xatolik yuz berdi.', level=messages.WARNING)


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('sale', 'product', 'quantity', 'price', 'discount', 'total', 'cost_price', 'profit')
    search_fields = ('sale__sale_number', 'product__name', 'product__code')
    autocomplete_fields = ('sale', 'product')
    readonly_fields = ('total', 'profit')
