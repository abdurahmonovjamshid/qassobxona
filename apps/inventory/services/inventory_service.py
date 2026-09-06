"""Inventory (ombor) uchun business logic.

Barcha ombor harakatlari shu servis orqali yaratiladi — boshqa app'lar
StockMovement'ni to'g'ridan-to'g'ri yaratmasligi kerak, aks holda
qoldiq hisob-kitobi buziladi.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.inventory.models import InventoryCount, StockMovement


def get_stock(product) -> Decimal:
    """Mahsulotning joriy ombor qoldig'ini (kg) qaytaradi (Total IN - Total OUT)."""
    total_in = StockMovement.objects.filter(
        product=product, direction=StockMovement.Direction.IN
    ).aggregate(s=Sum('quantity'))['s'] or Decimal('0')
    total_out = StockMovement.objects.filter(
        product=product, direction=StockMovement.Direction.OUT
    ).aggregate(s=Sum('quantity'))['s'] or Decimal('0')
    return total_in - total_out


def get_stock_pieces(product) -> int:
    """Mahsulotning joriy ombor qoldig'ini (dona/bo'lak soni) qaytaradi."""
    total_in = StockMovement.objects.filter(
        product=product, direction=StockMovement.Direction.IN
    ).aggregate(s=Sum('pieces'))['s'] or 0
    total_out = StockMovement.objects.filter(
        product=product, direction=StockMovement.Direction.OUT
    ).aggregate(s=Sum('pieces'))['s'] or 0
    return total_in - total_out


def get_all_stock() -> dict:
    """Har bir mahsulot uchun {product_id: qoldiq (kg)} lug'atini qaytaradi."""
    from apps.products.models import Product

    result = {}
    for product in Product.objects.all():
        result[product.id] = get_stock(product)
    return result


def get_all_stock_pieces() -> dict:
    """Har bir mahsulot uchun {product_id: qoldiq (dona)} lug'atini qaytaradi."""
    from apps.products.models import Product

    result = {}
    for product in Product.objects.all():
        result[product.id] = get_stock_pieces(product)
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
             pieces=0, reference='', created_by=None) -> StockMovement:
    """Omborga kirim yaratadi."""
    if quantity is None or quantity < 0:
        raise ValidationError('Ombor miqdori manfiy bolmasligi kerak.')
    if pieces is None or pieces < 0:
        raise ValidationError("Dona/bo'lak soni manfiy bolmasligi kerak.")
    if quantity == 0 and pieces == 0:
        raise ValidationError("Miqdor (kg) yoki dona sonidan kamida bittasi musbat bolishi kerak.")
    if unit_cost is None or unit_cost < 0:
        raise ValidationError('Tannarx manfiy bolmasligi kerak.')

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        pieces=pieces,
        movement_type=movement_type,
        direction=StockMovement.Direction.IN,
        unit_cost=unit_cost,
        reference=reference,
        date=date,
        created_by=created_by,
    )


def stock_out(*, product, quantity, movement_type, date, unit_cost=Decimal('0'),
              pieces=0, reference='', created_by=None) -> StockMovement:
    """Ombordan chiqim yaratadi. Qoldiq yetarli bo'lmasa xatolik beradi."""
    if quantity is None or quantity < 0:
        raise ValidationError('Ombor miqdori manfiy bolmasligi kerak.')
    if pieces is None or pieces < 0:
        raise ValidationError("Dona/bo'lak soni manfiy bolmasligi kerak.")
    if quantity == 0 and pieces == 0:
        raise ValidationError("Miqdor (kg) yoki dona sonidan kamida bittasi musbat bolishi kerak.")

    available = get_stock(product)
    if quantity > available:
        raise ValidationError(
            f"Omborda yetarli mahsulot mavjud emas. "
            f"Mavjud qoldiq: {available} {product.unit} ({product.name})"
        )
    available_pieces = get_stock_pieces(product)
    if pieces > available_pieces:
        raise ValidationError(
            f"Omborda yetarli dona/bo'lak mavjud emas. "
            f"Mavjud qoldiq: {available_pieces} dona ({product.name})"
        )

    return StockMovement.objects.create(
        product=product,
        quantity=quantity,
        pieces=pieces,
        movement_type=movement_type,
        direction=StockMovement.Direction.OUT,
        unit_cost=unit_cost,
        reference=reference,
        date=date,
        created_by=created_by,
    )


def _reference(count: InventoryCount) -> str:
    return f'INVCOUNT:{count.pk}'


@transaction.atomic
def confirm_inventory_count(count: InventoryCount, *, user=None) -> InventoryCount:
    """Inventarizatsiyani tasdiqlaydi: har bir mahsulot uchun tizim qoldig'i
    bilan hisoblangan qoldiq solishtirilib, farq ADJUSTMENT harakati bilan
    to'g'irlanadi (kg va dona alohida yo'nalishda bo'lishi mumkin).

    Agar item'da `unit_cost` to'ldirilgan bo'lsa (masalan Excel import orqali),
    tannarxni ham qayta belgilash uchun butun tizim qoldig'i chiqim qilinib,
    hisoblangan qoldiq shu tannarx bilan qayta kirim qilinadi — farqgina emas,
    to'liq miqdor (aks holda `unit_cost` yangi ADJUSTMENT-IN harakatiga
    tegishli bo'lib, o'rtacha tannarxni to'liq almashtira olmas edi)."""
    if count.status != InventoryCount.Status.DRAFT:
        raise ValidationError('Faqat DRAFT holatidagi inventarizatsiyani tasdiqlash mumkin.')

    items = list(count.items.select_related('product').all())
    if not items:
        raise ValidationError('Inventarizatsiyada kamida bitta mahsulot bolishi kerak.')

    reference = _reference(count)
    for item in items:
        system_kg = get_stock(item.product)
        system_pieces = get_stock_pieces(item.product)
        item.system_kg = system_kg
        item.system_pieces = system_pieces
        item.diff_kg = item.counted_kg - system_kg
        item.diff_pieces = item.counted_pieces - system_pieces
        item.save(update_fields=['system_kg', 'system_pieces', 'diff_kg', 'diff_pieces'])

        if item.unit_cost is not None:
            _apply_recount_with_cost(item, system_kg, system_pieces, reference, count.date, user)
        else:
            _apply_diff_only(item, reference, count.date, user)

    count.status = InventoryCount.Status.CONFIRMED
    count.save(update_fields=['status', 'updated_at'])
    return count


def _apply_diff_only(item, reference, date, user):
    """Eskicha rejim: faqat kg/dona farqi ADJUSTMENT bilan to'g'irlanadi,
    tannarxga tegilmaydi (qo'lda to'ldiriladigan Inventarizatsiya formasi)."""
    kg_in = item.diff_kg if item.diff_kg > 0 else Decimal('0')
    kg_out = -item.diff_kg if item.diff_kg < 0 else Decimal('0')
    pcs_in = item.diff_pieces if item.diff_pieces > 0 else 0
    pcs_out = -item.diff_pieces if item.diff_pieces < 0 else 0

    if kg_in > 0 or pcs_in > 0:
        stock_in(
            product=item.product, quantity=kg_in, pieces=pcs_in,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            reference=reference, date=date, created_by=user,
        )
    if kg_out > 0 or pcs_out > 0:
        stock_out(
            product=item.product, quantity=kg_out, pieces=pcs_out,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            reference=reference, date=date, created_by=user,
        )


def _apply_recount_with_cost(item, system_kg, system_pieces, reference, date, user):
    """Tannarx ham qayta belgilanadigan rejim: butun tizim qoldig'i chiqim
    qilinib, hisoblangan (Excel/qo'lda kiritilgan) qoldiq yangi tannarx bilan
    qayta kirim qilinadi. Bu shunchaki farqni emas, to'liq miqdorni
    ko'chirgani uchun `get_weighted_average_cost` yangi qiymatga yaqinroq
    (kichik/o'rtacha aylanma mahsulotlarda deyarli aniq) siljiydi."""
    if system_kg > 0 or system_pieces > 0:
        stock_out(
            product=item.product, quantity=system_kg, pieces=system_pieces,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            reference=reference, date=date, created_by=user,
        )
    if item.counted_kg > 0 or item.counted_pieces > 0:
        stock_in(
            product=item.product, quantity=item.counted_kg, pieces=item.counted_pieces,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            unit_cost=item.unit_cost, reference=reference, date=date, created_by=user,
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
                pieces=movement.pieces,
                movement_type=StockMovement.MovementType.ADJUSTMENT,
                direction=opposite,
                unit_cost=movement.unit_cost,
                reference=f'REVERSE:{reference}',
                date=date or movement.date,
                created_by=created_by,
            )
        )
    return created
