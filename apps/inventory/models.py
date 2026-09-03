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
        if self.quantity <= 0:
            raise ValidationError('Ombor miqdori musbat bolishi kerak.')
        if self.unit_cost < 0:
            raise ValidationError('Tannarx manfiy bolmasligi kerak.')

    def __str__(self):
        return f'{self.product} {self.direction} {self.quantity}'
