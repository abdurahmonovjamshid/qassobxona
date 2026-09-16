"""Sale (sotuv) uchun business logic."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.inventory.models import StockMovement
from apps.inventory.services import inventory_service
from apps.sales.models import Sale


def _reference(sale: Sale) -> str:
    return f'SALE:{sale.sale_number}'


def generate_sale_number() -> str:
    today = timezone.localdate()
    prefix = f"S{today.strftime('%Y%m%d')}"
    last = Sale.objects.filter(sale_number__startswith=prefix).order_by('-sale_number').first()
    seq = int(last.sale_number.rsplit('-', 1)[-1]) + 1 if last else 1
    return f"{prefix}-{seq:04d}"


@transaction.atomic
def confirm_sale(sale: Sale, *, user=None) -> Sale:
    """Sotuvni tasdiqlaydi: har bir mahsulot ombordan chiqadi (yetarli bolmasa xato),
    tannarx/foyda hisoblanadi va jami summa yangilanadi."""
    if sale.status != Sale.Status.DRAFT:
        raise ValidationError('Faqat DRAFT holatidagi sotuvni tasdiqlash mumkin.')
    if not sale.customer.active:
        raise ValidationError('Inactive mijozga sotuv qilib bolmaydi.')

    items = list(sale.items.select_related('product').all())
    if not items:
        raise ValidationError('Sotuvda kamida bitta mahsulot bolishi kerak.')

    reference = _reference(sale)
    total = Decimal('0')

    for item in items:
        if not item.product.active:
            raise ValidationError(f'"{item.product}" faol emas (inactive), sotib bolmaydi.')

        cost_price = inventory_service.get_weighted_average_cost(item.product)
        item.cost_price = cost_price
        item.save()  # SaleItem.save() total/profit'ni qayta hisoblaydi

        inventory_service.stock_out(
            product=item.product,
            quantity=item.quantity,
            pieces=item.pieces,
            movement_type=StockMovement.MovementType.SALE,
            unit_cost=cost_price,
            reference=reference,
            date=sale.date,
            created_by=user,
        )
        total += item.total

    sale.total_amount = total
    sale.status = Sale.Status.CONFIRMED
    sale.save()

    from apps.bot.admin_notify import notify_new_sale
    transaction.on_commit(lambda: notify_new_sale(sale, user=user))

    return sale


@transaction.atomic
def cancel_sale(sale: Sale, *, user=None) -> Sale:
    """Tasdiqlangan sotuvni bekor qiladi va ombor harakatlarini teskari qaytaradi."""
    if sale.status != Sale.Status.CONFIRMED:
        raise ValidationError('Faqat CONFIRMED holatidagi sotuvni bekor qilish mumkin.')

    inventory_service.reverse_movements(
        reference=_reference(sale),
        date=sale.date,
        created_by=user,
    )

    sale.status = Sale.Status.CANCELLED
    sale.save(update_fields=['status', 'updated_at'])
    return sale


def get_due_sales():
    """To'lov muddati kelgan (bugun yoki o'tib ketgan) va qarzi bor
    tasdiqlangan sotuvlar ro'yxati, muddat bo'yicha saralangan."""
    today = timezone.localdate()
    return (
        Sale.objects.filter(
            status=Sale.Status.CONFIRMED, debt_amount__gt=0,
            due_date__isnull=False, due_date__lte=today,
        )
        .select_related('customer').order_by('due_date')
    )


def recalc_sale_payment(sale: Sale) -> Sale:
    """Sale'ga bog'langan barcha Payment'lar yig'indisi asosida paid/debt'ni yangilaydi."""
    paid = sale.payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    sale.paid_amount = paid
    sale.save(update_fields=['paid_amount', 'debt_amount', 'updated_at'])
    return sale
