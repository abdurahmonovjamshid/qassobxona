"""Purchase (xarid) uchun business logic."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.common.allocation import allocate_proportionally
from apps.inventory.models import StockMovement
from apps.inventory.services import inventory_service
from apps.purchases.models import Purchase


def _reference(purchase: Purchase) -> str:
    return f'PURCHASE:{purchase.purchase_number}'


def generate_purchase_number() -> str:
    today = timezone.localdate()
    prefix = f"P{today.strftime('%Y%m%d')}"
    last = Purchase.objects.filter(purchase_number__startswith=prefix).order_by('-purchase_number').first()
    seq = int(last.purchase_number.rsplit('-', 1)[-1]) + 1 if last else 1
    return f"{prefix}-{seq:04d}"


@transaction.atomic
def confirm_purchase(purchase: Purchase, *, user=None) -> Purchase:
    """Xaridni tasdiqlaydi: har bir mahsulot (item) omborga kirim qilinadi,
    qo'shimcha xarajatlar (transport va h.k.) item'lar orasida NETTO VAZN (kg)
    ulushi bo'yicha taqsimlanib, yakuniy tannarxga (landed cost) qo'shiladi."""
    if purchase.status != Purchase.Status.DRAFT:
        raise ValidationError('Faqat DRAFT holatidagi xaridni tasdiqlash mumkin.')

    items = list(purchase.items.select_related('product').all())
    if not items:
        raise ValidationError('Xaridda kamida bitta mahsulot bolishi kerak.')

    reference = _reference(purchase)
    total_expenses = purchase.extra_expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    allocated_expenses = allocate_proportionally(total_expenses, items, lambda i: i.net_weight)

    total = Decimal('0')
    for item in items:
        allocated = allocated_expenses.get(item, Decimal('0'))
        expense_per_kg = (allocated / item.net_weight) if item.net_weight else Decimal('0')
        landed_unit_cost = (item.price_per_kg + expense_per_kg).quantize(Decimal('0.01'))

        item.total = (item.net_weight * item.price_per_kg).quantize(Decimal('0.01'))
        item.landed_unit_cost = landed_unit_cost
        item.save(update_fields=['total', 'landed_unit_cost'])

        inventory_service.stock_in(
            product=item.product,
            quantity=item.net_weight,
            pieces=item.pieces,
            movement_type=StockMovement.MovementType.PURCHASE,
            unit_cost=landed_unit_cost,
            reference=reference,
            date=purchase.date,
            created_by=user,
        )
        total += item.total

    purchase.total_amount = total
    purchase.status = Purchase.Status.CONFIRMED
    purchase.save()

    from apps.bot.admin_notify import notify_new_purchase
    transaction.on_commit(lambda: notify_new_purchase(purchase, user=user))

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
