from django import forms
from django.contrib import admin

from apps.kassa.services import cash_service

from .models import Payment
from .services import payment_service
from .services.payment_service import apply_cash_effect


class PaymentAdminForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            return cleaned
        if cleaned.get('payment_type') == Payment.PaymentType.CASH and cleaned.get('supplier'):
            amount = cleaned.get('amount') or 0
            balance = cash_service.get_balance()
            if amount > balance:
                raise forms.ValidationError(
                    f"Kassada yetarli mablag' yo'q. Joriy balans: {balance} so'm, "
                    f"talab qilingan: {amount} so'm."
                )
        return cleaned


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    form = PaymentAdminForm
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
        if not change:
            apply_cash_effect(obj, user=request.user)

    def delete_model(self, request, obj):
        payment_service.delete_payment(obj, user=request.user)

    def delete_queryset(self, request, queryset):
        for payment in queryset:
            payment_service.delete_payment(payment, user=request.user)
