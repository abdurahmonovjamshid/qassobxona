from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        PURCHASE = 'PURCHASE', 'Purchase'
        BUTCHERING_IN = 'BUTCHERING_IN', 'Butchering IN'
        BUTCHERING_OUT = 'BUTCHERING_OUT', 'Butchering OUT'
        SALE = 'SALE', 'Sale'
        RETURN = 'RETURN', 'Return'
        WASTE = 'WASTE', 'Waste'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'

    class Direction(models.TextChoices):
        IN = 'IN', 'In'
        OUT = 'OUT', 'Out'

    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='stock_movements')
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    pieces = models.PositiveIntegerField(default=0, help_text="Dona/bo'lak soni")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    direction = models.CharField(max_length=3, choices=Direction.choices)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reference = models.CharField(max_length=120, blank=True)
    date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def clean(self):
        if self.quantity < 0 or (self.pieces or 0) < 0:
            raise ValidationError('Ombor miqdori manfiy bolmasligi kerak.')
        if self.quantity == 0 and not self.pieces:
            raise ValidationError("Miqdor (kg) yoki dona sonidan kamida bittasi musbat bolishi kerak.")
        if self.unit_cost < 0:
            raise ValidationError('Tannarx manfiy bolmasligi kerak.')

    def __str__(self):
        return f'{self.product} {self.direction} {self.quantity}'


class InventoryCount(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'

    date = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f'Inventarizatsiya #{self.pk or "new"} ({self.date})'


class InventoryCountItem(models.Model):
    count = models.ForeignKey(InventoryCount, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='inventory_count_items')
    system_kg = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    system_pieces = models.IntegerField(default=0)
    counted_kg = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    counted_pieces = models.PositiveIntegerField(default=0)
    diff_kg = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    diff_pieces = models.IntegerField(default=0)
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="To'ldirilsa, ushbu mahsulot uchun tannarx shu qiymatga qayta "
                  "belgilanadi (butun qoldiq chiqim qilinib, shu tannarx bilan "
                  "qayta kirim qilinadi). Bo'sh qoldirilsa, tannarx o'zgarmaydi.",
    )

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.counted_kg is not None and self.counted_kg < 0:
            raise ValidationError("Hisoblangan miqdor manfiy bolmasligi kerak.")
        if self.unit_cost is not None and self.unit_cost < 0:
            raise ValidationError('Tannarx manfiy bolmasligi kerak.')

    def __str__(self):
        return f'{self.count} - {self.product}'
