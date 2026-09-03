"""Purchase (xarid) uchun business logic."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.inventory.models import StockMovement
from apps.inventory.services import inventory_service
from apps.purchases.models import Purchase


def _reference(purchase: Purchase) -> str:
    return f'PURCHASE:{purchase.purchase_number}'


@transaction.atomic
def confirm_purchase(purchase: Purchase, *, user=None) -> Purchase:
    """Xaridni tasdiqlaydi va mahsulotni omborga kirim qiladi."""
    if purchase.status != Purchase.Status.DRAFT:
        raise ValidationError('Faqat DRAFT holatidagi xaridni tasdiqlash mumkin.')
    if not purchase.product_id:
        raise ValidationError(
            'Xaridni tasdiqlash uchun avval "Mahsulot" (product) maydonini tanlang '
            '(masalan: "Mol (butun)") — shu mahsulot omborga kirim qilinadi.'
        )

    inventory_service.stock_in(
        product=purchase.product,
        quantity=purchase.net_weight,
        movement_type=StockMovement.MovementType.PURCHASE,
        unit_cost=purchase.price_per_kg,
        reference=_reference(purchase),
        date=purchase.date,
        created_by=user,
    )

    purchase.status = Purchase.Status.CONFIRMED
    purchase.save(update_fields=['status', 'updated_at'])
    return purchase


@transaction.atomic
def cancel_purchase(purchase: Purchase, *, user=None) -> Purchase:
    """Tasdiqlangan xaridni bekor qiladi va ombor harakatlarini teskari qaytaradi."""
    if purchase.status != Purchase.Status.CONFIRMED:
        raise ValidationError('Faqat CONFIRMED holatidagi xaridni bekor qilish mumkin.')
    if purchase.butcherings.exclude(status='CANCELLED').exists():
        raise ValidationError(
            'Bu xarid asosida tasdiqlangan bolaklash (Butchering) mavjud. '
            'Avval bolaklashni bekor qiling, keyin xaridni bekor qiling.'
        )

    inventory_service.reverse_movements(
        reference=_reference(purchase),
        date=purchase.date,
        created_by=user,
    )

    purchase.status = Purchase.Status.CANCELLED
    purchase.save(update_fields=['status', 'updated_at'])
    return purchase


def recalc_purchase_payment(purchase: Purchase) -> Purchase:
    """Purchase'ga bog'langan barcha Payment'lar yig'indisi asosida paid/debt'ni yangilaydi."""
    paid = purchase.payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    purchase.paid_amount = paid
    purchase.save(update_fields=['paid_amount', 'debt_amount', 'updated_at'])
    return purchase
