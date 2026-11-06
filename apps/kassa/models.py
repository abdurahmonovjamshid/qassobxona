from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CashRegister(models.Model):
    """Kassa: "Naqd kassa" (CASH) va "Karta kassa" (CARD). `code` to'lov
    turiga (Payment.PaymentType) mos keladi — Naqd to'lov naqd kassaga,
    karta to'lov karta kassaga yoziladi."""

    class Code(models.TextChoices):
        CASH = 'CASH', 'Naqd kassa'
        CARD = 'CARD', 'Karta kassa'

    name = models.CharField(max_length=80)
    code = models.CharField(max_length=10, choices=Code.choices, unique=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_default', 'id']

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        register = cls.objects.filter(is_default=True).first() or cls.objects.filter(code=cls.Code.CASH).first()
        if register is None:
            register = cls.objects.create(name='Naqd kassa', code=cls.Code.CASH, is_default=True)
        return register

    @classmethod
    def for_payment_type(cls, payment_type):
        """CASH -> Naqd kassa, CARD -> Karta kassa, boshqalar (o'tkazma va h.k.) -> None."""
        if payment_type == cls.Code.CASH:
            return cls.objects.filter(code=cls.Code.CASH).first() or cls.get_default()
        if payment_type == cls.Code.CARD:
            return cls.objects.get_or_create(code=cls.Code.CARD, defaults={'name': 'Karta kassa'})[0]
        return None


class CashTransaction(models.Model):
    """Kassa harakati (ledger yozuvi). `amount` ishorali: musbat — kirim,
    manfiy — chiqim. Balans barcha yozuvlar yig'indisi sifatida hisoblanadi
    (StockMovement'dagi kabi append-only tarix)."""

    class TransactionType(models.TextChoices):
        OPENING = 'OPENING', "Boshlang'ich balans"
        SALE_PAYMENT = 'SALE_PAYMENT', "Mijozdan to'lov"
        PURCHASE_PAYMENT = 'PURCHASE_PAYMENT', "Yetkazib beruvchiga to'lov"
        SALE_REFUND = 'SALE_REFUND', "Mijozga qaytarim"
        PURCHASE_REFUND = 'PURCHASE_REFUND', "Yetkazib beruvchidan qaytarim"
        EXPENSE = 'EXPENSE', 'Xarajat'
        ADJUSTMENT = 'ADJUSTMENT', "Qo'lda tuzatish (admin)"

    register = models.ForeignKey(CashRegister, on_delete=models.PROTECT, related_name="transactions",
                                 verbose_name='Kassa')
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
