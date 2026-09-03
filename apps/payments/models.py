from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Payment(models.Model):
    class PaymentType(models.TextChoices):
        CASH = 'CASH', 'Cash'
        CARD = 'CARD', 'Card'
        TRANSFER = 'TRANSFER', 'Transfer'
        OTHER = 'OTHER', 'Other'

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices, default=PaymentType.CASH)
    customer = models.ForeignKey('customers.Customer', on_delete=models.PROTECT, null=True, blank=True, related_name='payments')
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.PROTECT, null=True, blank=True, related_name='payments')
    sale = models.ForeignKey('sales.Sale', on_delete=models.PROTECT, null=True, blank=True, related_name='payments')
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.PROTECT, null=True, blank=True, related_name='payments')
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def clean(self):
        if self.amount <= 0:
            raise ValidationError('Tolov musbat bolishi kerak.')
        if self.customer and self.supplier:
            raise ValidationError('Tolov bir vaqtda customer va supplierga tegishli bolmasin.')
        if not self.customer and not self.supplier:
            raise ValidationError('Tolov customer yoki supplierga boglanishi kerak.')

    def __str__(self):
        owner = self.customer or self.supplier
        return f'{owner} - {self.amount}'
