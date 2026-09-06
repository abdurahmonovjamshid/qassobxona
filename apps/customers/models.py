from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    opening_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Boshlang'ich saldo (musbat = mijoz qarzdor).",
    )
    is_supplier = models.BooleanField(
        default=False, help_text="Bu mijoz shu bilan birga yetkazib beruvchi ham.",
    )
    linked_supplier = models.OneToOneField(
        'suppliers.Supplier', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='linked_customer',
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
