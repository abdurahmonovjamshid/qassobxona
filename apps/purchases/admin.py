from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Purchase, PurchaseExpense, PurchaseItem
from .services import purchase_service


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1
    readonly_fields = ('total', 'landed_unit_cost')


class PurchaseExpenseInline(admin.TabularInline):
    model = PurchaseExpense
    extra = 1


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'purchase_number', 'supplier', 'date', 'total_amount', 'paid_amount', 'debt_amount', 'status',
    )
    list_filter = ('status', 'date')
    search_fields = ('purchase_number', 'supplier__name', 'notes')
    autocomplete_fields = ('supplier', 'created_by')
    readonly_fields = ('total_amount', 'debt_amount', 'status', 'created_at', 'updated_at')
    date_hierarchy = 'date'
    ordering = ('-date', '-id')
    inlines = (PurchaseItemInline, PurchaseExpenseInline)
    actions = ('confirm_purchases', 'cancel_purchases')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="✅ Tanlangan xaridlarni tasdiqlash (omborga kirim qiladi)")
    def confirm_purchases(self, request, queryset):
        ok, failed = 0, 0
        for purchase in queryset:
            try:
                purchase_service.confirm_purchase(purchase, user=request.user)
                ok += 1
            except ValidationError as exc:
                failed += 1
                self.message_user(request, f'{purchase}: {"; ".join(exc.messages)}', level=messages.ERROR)
        if ok:
            self.message_user(request, f'{ok} ta xarid tasdiqlandi.', level=messages.SUCCESS)
        if failed:
            self.message_user(request, f'{failed} ta xaridda xatolik yuz berdi.', level=messages.WARNING)

    @admin.action(description="❌ Tanlangan xaridlarni bekor qilish")
    def cancel_purchases(self, request, queryset):
        ok, failed = 0, 0
        for purchase in queryset:
            try:
                purchase_service.cancel_purchase(purchase, user=request.user)
                ok += 1
            except ValidationError as exc:
                failed += 1
                self.message_user(request, f'{purchase}: {"; ".join(exc.messages)}', level=messages.ERROR)
        if ok:
            self.message_user(request, f'{ok} ta xarid bekor qilindi.', level=messages.SUCCESS)
        if failed:
            self.message_user(request, f'{failed} ta xaridda xatolik yuz berdi.', level=messages.WARNING)


@admin.register(PurchaseExpense)
class PurchaseExpenseAdmin(admin.ModelAdmin):
    list_display = ('purchase', 'expense_type', 'amount')
    list_filter = ('expense_type',)
    search_fields = ('purchase__purchase_number', 'notes')
    autocomplete_fields = ('purchase',)
