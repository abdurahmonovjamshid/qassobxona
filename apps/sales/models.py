from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Sale(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    customer = models.ForeignKey('customers.Customer', on_delete=models.PROTECT, related_name='sales')
    sale_number = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    debt_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
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
        return self.sale_number


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='sale_items')
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    pieces = models.PositiveIntegerField(default=0, help_text="Dona/bo'lak soni")
    price = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.quantity is None or self.price is None:
            return
        if self.quantity <= 0:
            raise ValidationError('Miqdor musbat bolishi kerak.')
        if self.price < 0 or (self.discount or 0) < 0 or (self.cost_price or 0) < 0:
            raise ValidationError('Summa manfiy bolmasligi kerak.')

    def save(self, *args, **kwargs):
        self.total = (self.quantity * self.price) - self.discount
        self.profit = self.total - (self.quantity * self.cost_price)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.sale} - {self.product}'
