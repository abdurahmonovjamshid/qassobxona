from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CashTransaction(models.Model):
    """Kassa harakati (ledger yozuvi). `amount` ishorali: musbat — kirim,
    manfiy — chiqim. Balans barcha yozuvlar yig'indisi sifatida hisoblanadi
    (StockMovement'dagi kabi append-only tarix)."""

    class TransactionType(models.TextChoices):
        OPENING = 'OPENING', "Boshlang'ich balans"
        SALE_PAYMENT = 'SALE_PAYMENT', "Mijozdan naqd to'lov"
        PURCHASE_PAYMENT = 'PURCHASE_PAYMENT', "Yetkazib beruvchiga naqd to'lov"
        EXPENSE = 'EXPENSE', 'Xarajat'
        ADJUSTMENT = 'ADJUSTMENT', "Qo'lda tuzatish (admin)"

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def clean(self):
        if self.amount == 0:
            raise ValidationError('Summa nolga teng bolmasligi kerak.')

    def __str__(self):
        return f'{self.get_transaction_type_display()} {self.amount}'
