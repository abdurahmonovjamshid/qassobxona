from decimal import Decimal

from django.db import models
from django.db.models import Sum


class Supplier(models.Model):
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    opening_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Boshlang'ich saldo (musbat = bizning qarzimiz).",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_total_purchases(self) -> Decimal:
        from apps.purchases.models import Purchase
        return self.purchases.filter(status=Purchase.Status.CONFIRMED).aggregate(
            s=Sum('total_amount'))['s'] or Decimal('0')

    def get_total_payments(self) -> Decimal:
        """Yetkazib beruvchiga berilgan sof to'lov: unga to'langan pul minus
        undan qaytarib olingan pul. Ikkinchisi — mijoz pulni to'g'ridan-to'g'ri
        yetkazib beruvchining hisobiga o'tkazgani sababli u yerda yig'ilib
        qolgan avansni naqd yechib olish holati.

        Bekor qilingan xarid/sotuvga bog'langan to'lovlar hisobga olinmaydi —
        aks holda bekor qilingan xaridning to'lovi qarzni haqiqatidan kamroq
        ko'rsatib qo'yardi."""
        from apps.payments.models import Payment, active_payments, net_payment_sum
        return net_payment_sum(
            active_payments(self.payments), positive_direction=Payment.Direction.OUT,
        )

    def get_total_debt(self) -> Decimal:
        """Boshlang'ich saldo + jami xarid - jami to'lov (xaridga bog'liq
        bo'lmagan umumiy to'lovlar ham hisobga olinadi). Natija manfiy bo'lishi
        normal — bu yetkazib beruvchida bizning avansimiz turganini bildiradi."""
        return self.opening_balance + self.get_total_purchases() - self.get_total_payments()
