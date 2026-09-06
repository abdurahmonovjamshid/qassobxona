from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Purchase(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.PROTECT, related_name='purchases')
    purchase_number = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    debt_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']

    def clean(self):
        if self.total_amount < 0 or self.paid_amount < 0:
            raise ValidationError('Summa manfiy bolmasligi kerak.')

    def save(self, *args, **kwargs):
        self.debt_amount = self.total_amount - self.paid_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return self.purchase_number


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='purchase_items')
    net_weight = models.DecimalField(max_digits=10, decimal_places=3)
    pieces = models.PositiveIntegerField(default=0, help_text="Dona/bo'lak soni")
    price_per_kg = models.DecimalField(max_digits=14, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    landed_unit_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Qo'shimcha xarajatlar qo'shilgan yakuniy tannarx/kg",
    )

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.net_weight is None:
            return
        if self.net_weight <= 0:
            raise ValidationError('Vazn musbat bolishi kerak.')
        if self.price_per_kg is not None and self.price_per_kg < 0:
            raise ValidationError('Narx manfiy bolmasligi kerak.')

    def save(self, *args, **kwargs):
        self.total = (self.net_weight * self.price_per_kg).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.purchase} - {self.product}'


class PurchaseExpense(models.Model):
    class ExpenseType(models.TextChoices):
        TRANSPORT = 'TRANSPORT', 'Transport'
        LOADING = 'LOADING', 'Yuklash'
        UNLOADING = 'UNLOADING', 'Tushirish'
        SLAUGHTER = 'SLAUGHTER', 'Soyish'
        OTHER = 'OTHER', 'Boshqa'

    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='extra_expenses')
    expense_type = models.CharField(max_length=20, choices=ExpenseType.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.amount is None:
            return
        if self.amount < Decimal('0'):
            raise ValidationError('Xarajat manfiy bolmasligi kerak.')

    def __str__(self):
        return f'{self.purchase} - {self.expense_type}'
