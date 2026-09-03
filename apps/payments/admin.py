from django.contrib import admin

from .models import Payment
from .services import payment_service


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('date', 'amount', 'payment_type', 'customer', 'supplier', 'sale', 'purchase')
    list_filter = ('payment_type', 'date')
    search_fields = (
        'customer__name', 'supplier__name', 'sale__sale_number',
        'purchase__purchase_number', 'notes',
    )
    autocomplete_fields = ('customer', 'supplier', 'sale', 'purchase', 'created_by')
    readonly_fields = ('created_at',)
    date_hierarchy = 'date'
    ordering = ('-date', '-id')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        # Payment saqlangandan keyin bog'liq Sale/Purchase'ning
        # paid_amount/debt_amount maydonlarini qayta hisoblaymiz.
        if obj.sale_id:
            from apps.sales.services import sale_service
            sale_service.recalc_sale_payment(obj.sale)
        if obj.purchase_id:
            from apps.purchases.services import purchase_service
            purchase_service.recalc_purchase_payment(obj.purchase)

    def delete_model(self, request, obj):
        payment_service.delete_payment(obj)

    def delete_queryset(self, request, queryset):
        for payment in queryset:
            payment_service.delete_payment(payment)
