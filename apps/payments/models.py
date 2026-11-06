from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, DecimalField, F, Sum, When


class Payment(models.Model):
    class PaymentType(models.TextChoices):
        CASH = 'CASH', 'Naqd'
        CARD = 'CARD', 'Karta'
        TRANSFER = 'TRANSFER', "O'tkazma"
        OTHER = 'OTHER', 'Boshqa'

    class Direction(models.TextChoices):
        """Pulning yo'nalishi. Avval bu maydon yo'q edi va yo'nalish
        `customer`/`supplier` maydonidan taxmin qilinardi (mijoz — kirim,
        yetkazib beruvchi — chiqim). Lekin ikkala tomonda ham teskari holat
        bo'ladi: mijozga pul qaytarish, yoki yetkazib beruvchida yig'ilib
        qolgan avansni undan qaytarib olish."""

        IN = 'IN', "Kirim (pul bizga keldi)"
        OUT = 'OUT', "Chiqim (pul bizdan ketdi)"

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    direction = models.CharField(max_length=3, choices=Direction.choices, default=Direction.IN)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices, default=PaymentType.CASH)
    cash_register = models.ForeignKey(
        'kassa.CashRegister', on_delete=models.PROTECT, null=True, blank=True, related_name='payments',
        verbose_name='Kassa', help_text="Pul qaysi kassaga kirdi/chiqdi (bo'sh — kassaga ta'sir qilmaydi)",
    )
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

    @property
    def is_incoming(self) -> bool:
        return self.direction == self.Direction.IN

    @property
    def signed_amount(self) -> Decimal:
        """Kassa nuqtai nazaridan ishorali summa: kirim musbat, chiqim manfiy."""
        return self.amount if self.is_incoming else -self.amount

    def clean(self):
        if self.amount <= 0:
            raise ValidationError('Tolov musbat bolishi kerak.')
        if self.customer and self.supplier:
            raise ValidationError('Tolov bir vaqtda customer va supplierga tegishli bolmasin.')
        if not self.customer and not self.supplier:
            raise ValidationError('Tolov customer yoki supplierga boglanishi kerak.')

    def __str__(self):
        owner = self.customer or self.supplier
        arrow = '←' if self.is_incoming else '→'
        return f'{owner} {arrow} {self.amount}'


def active_payments(queryset):
    """Bekor qilingan sotuv/xaridga bog'langan to'lovlarni chiqarib tashlaydi.

    Qarz hisobida bekor qilingan hujjatning summasi hisobga olinmaydi, shuning
    uchun uning to'lovi ham hisobga olinmasligi kerak — aks holda qarz
    haqiqatidan kamroq ko'rinardi. Bu qoida qarzga oid har bir joyda (saldo,
    akt-sverka, dashboard, tranzaksiyalar tarixi) bir xil bo'lishi uchun shu
    yagona funksiyada saqlanadi.

    Diqqat: bu faqat QARZ hisobiga tegishli. Bekor qilingan sotuvning naqd
    to'lovi kassadan avtomatik chiqarilmaydi (pul haqiqatda qo'lda turadi),
    shuning uchun kassa summalariga bu filtr qo'llanilmaydi."""
    from apps.purchases.models import Purchase
    from apps.sales.models import Sale
    from django.db.models import Q
    return queryset.exclude(
        Q(sale__status=Sale.Status.CANCELLED) | Q(purchase__status=Purchase.Status.CANCELLED)
    )


def net_payment_sum(queryset, *, positive_direction) -> Decimal:
    """`queryset`dagi to'lovlarning ishorali yig'indisi.

    `positive_direction` — qaysi yo'nalish "qarzni kamaytiradi" degani.
    Mijoz uchun bu IN (mijozdan pul olsak qarzi kamayadi), yetkazib beruvchi
    uchun OUT (unga to'lasak qarzimiz kamayadi). Teskari yo'nalishdagi to'lov
    yig'indidan ayiriladi, shuning uchun mijozga qaytarilgan pul yoki
    yetkazib beruvchidan qaytarib olingan avans qarzni oshiradi."""
    total = queryset.aggregate(s=Sum(Case(
        When(direction=positive_direction, then=F('amount')),
        default=-F('amount'),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )))['s']
    return total if total is not None else Decimal('0')
