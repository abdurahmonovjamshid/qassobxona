"""Inventory (ombor) uchun business logic.

Barcha ombor harakatlari shu servis orqali yaratiladi — boshqa app'lar
StockMovement'ni to'g'ridan-to'g'ri yaratmasligi kerak, aks holda
qoldiq hisob-kitobi buziladi.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from apps.inventory.models import StockMovement


def get_stock(product) -> Decimal:
    """Mahsulotning joriy ombor qoldig'ini qaytaradi (Total IN - Total OUT)."""
    total_in = StockMovement.objects.filter(
        product=product, direction=StockMovement.Direction.IN
    ).aggregate(s=Sum('quantity'))['s'] or Decimal('0')
    total_out = StockMovement.objects.filter(
        product=product, direction=StockMovement.Direction.OUT
    ).aggregate(s=Sum('quantity'))['s'] or Decimal('0')
    return total_in - total_out


def get_all_stock() -> dict:
    """Har bir mahsulot uchun {product_id: qoldiq} lug'atini qaytaradi."""
    from apps.products.models import Product

    result = {}
    for product in Product.objects.all():
        result[product.id] = get_stock(product)
    return result


def get_weighted_average_cost(product) -> Decimal:
    """Mahsulotning kirim harakatlari bo'yicha o'rtacha tannarxini hisoblaydi."""
    ins = StockMovement.objects.filter(product=product, direction=StockMovement.Direction.IN)
    total_qty = ins.aggregate(s=Sum('quantity'))['s'] or Decimal('0')
    if total_qty <= 0:
        return Decimal('0')
    total_cost = Decimal('0')
    for movement in ins.only('quantity', 'unit_cost'):
        total_cost += movement.quantity * movement.unit_cost
    return (total_cost / total_qty).quantize(Decimal('0.01'))


def stock_in(*, product, quantity, movement_type, date, unit_cost=Decimal('0'),
             reference='', created_by=None) -> StockMovement:
    """Omborga kirim yaratadi."""
    if quantity is None or quantity <= 0:
        raise ValidationError('Ombor miqdori musbat bolishi kerak.')
    if unit_cost is None or unit_cost < 0:
        raise ValidationError('Tannarx manfiy bolmasligi kerak.')

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=movement_type,
        direction=StockMovement.Direction.IN,
        unit_cost=unit_cost,
        reference=reference,
        date=date,
        created_by=created_by,
    )


def stock_out(*, product, quantity, movement_type, date, unit_cost=Decimal('0'),
              reference='', created_by=None) -> StockMovement:
    """Ombordan chiqim yaratadi. Qoldiq yetarli bo'lmasa xatolik beradi."""
    if quantity is None or quantity <= 0:
        raise ValidationError('Ombor miqdori musbat bolishi kerak.')

    available = get_stock(product)
    if quantity > available:
        raise ValidationError(
            f"Omborda yetarli mahsulot mavjud emas. "
            f"Mavjud qoldiq: {available} {product.unit} ({product.name})"
        )

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        movement_type=movement_type,
        direction=StockMovement.Direction.OUT,
        unit_cost=unit_cost,
        reference=reference,
        date=date,
        created_by=created_by,
    )


def reverse_movements(*, reference, date=None, created_by=None) -> list:
    """`reference` bo'yicha barcha harakatlarni teskarisiga qaytaradi (bekor qilish uchun).

    Asl harakatlar o'chirilmaydi (tarix saqlanadi) — ularga qarama-qarshi
    yo'nalishda yangi ADJUSTMENT harakatlari qo'shiladi.
    """
    movements = StockMovement.objects.filter(reference=reference)
    created = []
    for movement in movements:
        opposite = (
            StockMovement.Direction.OUT
            if movement.direction == StockMovement.Direction.IN
            else StockMovement.Direction.IN
        )
        created.append(
            StockMovement.objects.create(
                product=movement.product,
                quantity=movement.quantity,
                movement_type=StockMovement.MovementType.ADJUSTMENT,
                direction=opposite,
                unit_cost=movement.unit_cost,
                reference=f'REVERSE:{reference}',
                date=date or movement.date,
                created_by=created_by,
            )
        )
    return created
