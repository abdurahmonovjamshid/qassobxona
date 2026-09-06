from django import forms
from django.contrib import admin

from .models import CashTransaction


class CashTransactionAdminForm(forms.ModelForm):
    class Meta:
        model = CashTransaction
        fields = ['amount', 'date', 'notes']
        help_texts = {
            'amount': "Musbat = kassaga kirim, manfiy = kassadan chiqim.",
        }


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    """Kassa balansini qo'lda tuzatish FAQAT shu yerdan (Django admin, superuser)
    amalga oshiriladi — ilova ichidagi sahifalar balansni faqat o'qiydi."""

    list_display = ('date', 'transaction_type', 'amount', 'reference', 'created_by')
    list_filter = ('transaction_type', 'date')
    search_fields = ('reference', 'notes')
    date_hierarchy = 'date'
    ordering = ('-date', '-id')

    def get_readonly_fields(self, request, obj=None):
        # Tizim o'zi yozgan yozuvlar (SALE_PAYMENT, PURCHASE_PAYMENT, EXPENSE)
        # tahrirlanmasin — faqat qo'lda ADJUSTMENT yaratish/ko'rish mumkin.
        if obj and obj.transaction_type != CashTransaction.TransactionType.ADJUSTMENT:
            return [f.name for f in self.model._meta.fields]
        return ('transaction_type', 'created_by', 'created_at') if obj else ('created_by', 'created_at')

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = CashTransactionAdminForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.transaction_type = CashTransaction.TransactionType.ADJUSTMENT
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.transaction_type != CashTransaction.TransactionType.ADJUSTMENT:
            return False
        return super().has_delete_permission(request, obj)
