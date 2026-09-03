from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Butchering(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.PROTECT, related_name='butcherings')
    input_product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='butchering_inputs')
    input_weight = models.DecimalField(max_digits=10, decimal_places=3)
    output_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    difference = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    yield_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']

    def clean(self):
        if self.input_weight <= 0:
            raise ValidationError('Input vazn musbat bolishi kerak.')
        if self.output_weight > self.input_weight:
            raise ValidationError('Output inputdan katta bolmasligi kerak.')

    def __str__(self):
        return f'Butchering #{self.pk or "new"}'


class ButcheringOutput(models.Model):
    butchering = models.ForeignKey(Butchering, on_delete=models.CASCADE, related_name='outputs')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='butchering_outputs')
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.quantity is None:
            return
        if self.quantity <= 0:
            raise ValidationError('Output miqdori musbat bolishi kerak.')

    def __str__(self):
        return f'{self.product} - {self.quantity} kg'
