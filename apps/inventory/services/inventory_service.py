"""Inventory (ombor) uchun business logic.

Barcha ombor harakatlari shu servis orqali yaratiladi — boshqa app'lar
StockMovement'ni to'g'ridan-to'g'ri yaratmasligi kerak, aks holda
qoldiq hisob-kitobi buziladi.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.inventory.models import InventoryCount, StockMovement, StockTransfer, Warehouse


def resolve_warehouse(warehouse) -> Warehouse:
    """`None` berilsa asosiy (default) omborni qaytaradi."""
    return warehouse or Warehouse.get_default()


def _movements(product, warehouse=None):
    qs = StockMovement.objects.filter(product=product)
    if warehouse is not None:
        qs = qs.filter(warehouse=warehouse)
    return qs


def get_stock(product, warehouse=None) -> Decimal:
    """Mahsulotning joriy ombor qoldig'ini (kg) qaytaradi (Total IN - Total OUT).
    `warehouse` berilmasa barcha omborlar bo'yicha jami qoldiq."""
    qs = _movements(product, warehouse)
    total_in = qs.filter(direction=StockMovement.Direction.IN).aggregate(s=Sum('quantity'))['s'] or Decimal('0')
    total_out = qs.filter(direction=StockMovement.Direction.OUT).aggregate(s=Sum('quantity'))['s'] or Decimal('0')
    return total_in - total_out


def get_stock_pieces(product, warehouse=None) -> int:
    """Mahsulotning joriy ombor qoldig'ini (dona/bo'lak soni) qaytaradi."""
    qs = _movements(product, warehouse)
    total_in = qs.filter(direction=StockMovement.Direction.IN).aggregate(s=Sum('pieces'))['s'] or 0
    total_out = qs.filter(direction=StockMovement.Direction.OUT).aggregate(s=Sum('pieces'))['s'] or 0
    return total_in - total_out


def _stock_map(field, warehouse=None) -> dict:
    qs = StockMovement.objects.all()
    if warehouse is not None:
        qs = qs.filter(warehouse=warehouse)
    result = {}
    for row in qs.values('product_id', 'direction').annotate(s=Sum(field)):
        sign = 1 if row['direction'] == StockMovement.Direction.IN else -1
        result[row['product_id']] = result.get(row['product_id'], 0) + sign * (row['s'] or 0)
    return result


def get_all_stock(warehouse=None) -> dict:
    """Har bir mahsulot uchun {product_id: qoldiq (kg)} lug'atini qaytaradi."""
    from apps.products.models import Product

    totals = _stock_map('quantity', warehouse)
    return {pid: totals.get(pid, Decimal('0')) for pid in Product.objects.values_list('id', flat=True)}


def get_all_stock_pieces(warehouse=None) -> dict:
    """Har bir mahsulot uchun {product_id: qoldiq (dona)} lug'atini qaytaradi."""
    from apps.products.models import Product

    totals = _stock_map('pieces', warehouse)
    return {pid: totals.get(pid, 0) for pid in Product.objects.values_list('id', flat=True)}


def get_weighted_average_cost(product) -> Decimal:
    """Mahsulotning joriy qoldig'i uchun o'rtacha tannarxni (moving average)
    hisoblaydi.

    Harakatlar kiritilgan tartibda qayta o'ynaladi: kirim qoldiq qiymatiga
    o'z tannarxi bilan qo'shiladi, chiqim esa o'sha paytdagi o'rtacha tannarx
    bilan ayiriladi. Shu sababli allaqachon sotilib ketgan partiya keyingi
    xaridning tannarxiga ta'sir qilmaydi (masalan: 100 kg 70 000 dan olinib
    sotilsa, ertasi 60 000 dan olingan tovar tannarxi 60 000 bo'ladi).
    Qoldiq nolga tushganda qiymat ham nolga qaytariladi."""
    qty = Decimal('0')
    value = Decimal('0')
    movements = (
        StockMovement.objects.filter(product=product)
        .order_by('id').values_list('direction', 'quantity', 'unit_cost')
    )
    for direction, quantity, unit_cost in movements:
        if direction == StockMovement.Direction.IN:
            if qty <= 0:
                qty, value = Decimal('0'), Decimal('0')
            qty += quantity
            value += quantity * unit_cost
        else:
            avg = value / qty if qty > 0 else Decimal('0')
            qty -= quantity
            value -= quantity * avg
            if qty <= 0:
                qty, value = Decimal('0'), Decimal('0')
    if qty <= 0:
        return Decimal('0')
    return (value / qty).quantize(Decimal('0.01'))


def stock_in(*, product, quantity, movement_type, date, unit_cost=Decimal('0'),
             pieces=0, reference='', created_by=None, warehouse=None) -> StockMovement:
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
        warehouse=resolve_warehouse(warehouse),
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
              pieces=0, reference='', created_by=None, warehouse=None) -> StockMovement:
    """Ombordan chiqim yaratadi. Qoldiq yetarli bo'lmasa xatolik beradi."""
    if quantity is None or quantity < 0:
        raise ValidationError('Ombor miqdori manfiy bolmasligi kerak.')
    if pieces is None or pieces < 0:
        raise ValidationError("Dona/bo'lak soni manfiy bolmasligi kerak.")
    if quantity == 0 and pieces == 0:
        raise ValidationError("Miqdor (kg) yoki dona sonidan kamida bittasi musbat bolishi kerak.")

    warehouse = resolve_warehouse(warehouse)
    available = get_stock(product, warehouse)
    if quantity > available:
        raise ValidationError(
            f"Omborda ({warehouse.name}) yetarli mahsulot mavjud emas. "
            f"Mavjud qoldiq: {available} {product.unit} ({product.name})"
        )
    available_pieces = get_stock_pieces(product, warehouse)
    if pieces > available_pieces:
        raise ValidationError(
            f"Omborda ({warehouse.name}) yetarli dona/bo'lak mavjud emas. "
            f"Mavjud qoldiq: {available_pieces} dona ({product.name})"
        )

    return StockMovement.objects.create(
        product=product,
        warehouse=warehouse,
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
    warehouse = resolve_warehouse(count.warehouse)
    for item in items:
        system_kg = get_stock(item.product, warehouse)
        system_pieces = get_stock_pieces(item.product, warehouse)
        item.system_kg = system_kg
        item.system_pieces = system_pieces
        item.diff_kg = item.counted_kg - system_kg
        item.diff_pieces = item.counted_pieces - system_pieces
        item.save(update_fields=['system_kg', 'system_pieces', 'diff_kg', 'diff_pieces'])

        if item.unit_cost is not None:
            _apply_recount_with_cost(item, system_kg, system_pieces, reference, count.date, user, warehouse)
        else:
            _apply_diff_only(item, reference, count.date, user, warehouse)

    count.status = InventoryCount.Status.CONFIRMED
    count.save(update_fields=['status', 'updated_at'])
    return count


def inventory_difference(date_from, date_to) -> dict:
    """Tasdiqlangan inventarizatsiyalardagi farq (hisoblangan − tizim qoldig'i)
    shu davr uchun: kamomad va ortiqcha kg hamda so'mdagi qiymati. Qiymat
    item tannarxi (Excel importda kiritilgan) yoki mahsulotning joriy o'rtacha
    tannarxi bilan hisoblanadi."""
    from apps.inventory.models import InventoryCountItem

    items = InventoryCountItem.objects.filter(
        count__status=InventoryCount.Status.CONFIRMED,
        count__date__gte=date_from, count__date__lte=date_to,
    ).exclude(diff_kg=0).select_related('product')
    costs = {}
    shortage_kg = surplus_kg = shortage_value = surplus_value = Decimal('0')
    for item in items:
        cost = item.unit_cost
        if cost is None:
            if item.product_id not in costs:
                costs[item.product_id] = get_weighted_average_cost(item.product)
            cost = costs[item.product_id]
        value = item.diff_kg * cost
        if item.diff_kg < 0:
            shortage_kg += -item.diff_kg
            shortage_value += -value
        else:
            surplus_kg += item.diff_kg
            surplus_value += value
    return {
        'shortage_kg': shortage_kg, 'shortage_value': shortage_value,
        'surplus_kg': surplus_kg, 'surplus_value': surplus_value,
        'net_value': surplus_value - shortage_value,
    }


def _apply_diff_only(item, reference, date, user, warehouse):
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
            reference=reference, date=date, created_by=user, warehouse=warehouse,
        )
    if kg_out > 0 or pcs_out > 0:
        stock_out(
            product=item.product, quantity=kg_out, pieces=pcs_out,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            reference=reference, date=date, created_by=user, warehouse=warehouse,
        )


def _apply_recount_with_cost(item, system_kg, system_pieces, reference, date, user, warehouse):
    """Tannarx ham qayta belgilanadigan rejim: butun tizim qoldig'i chiqim
    qilinib, hisoblangan (Excel/qo'lda kiritilgan) qoldiq yangi tannarx bilan
    qayta kirim qilinadi. Bu shunchaki farqni emas, to'liq miqdorni
    ko'chirgani uchun `get_weighted_average_cost` yangi qiymatga yaqinroq
    (kichik/o'rtacha aylanma mahsulotlarda deyarli aniq) siljiydi."""
    # Qoldiq manfiy bo'lishi mumkin (ALLOW_NEGATIVE_STOCK): musbat qismi chiqim
    # qilinadi, manfiy qismi esa kirimga qo'shiladi — natijada qoldiq aynan
    # hisoblangan miqdorga (masalan 0 ga) teng bo'ladi.
    out_kg = max(system_kg, Decimal('0'))
    out_pieces = max(system_pieces, 0)
    in_kg = item.counted_kg + max(-system_kg, Decimal('0'))
    in_pieces = item.counted_pieces + max(-system_pieces, 0)
    if out_kg > 0 or out_pieces > 0:
        stock_out(
            product=item.product, quantity=out_kg, pieces=out_pieces,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            reference=reference, date=date, created_by=user, warehouse=warehouse,
        )
    if in_kg > 0 or in_pieces > 0:
        stock_in(
            product=item.product, quantity=in_kg, pieces=in_pieces,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            unit_cost=item.unit_cost, reference=reference, date=date, created_by=user, warehouse=warehouse,
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
                warehouse=movement.warehouse,
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


def _transfer_reference(transfer: StockTransfer) -> str:
    return f'TRANSFER:{transfer.pk}'


@transaction.atomic
def confirm_transfer(transfer: StockTransfer, *, user=None) -> StockTransfer:
    """Ko'chirishni tasdiqlaydi: har bir mahsulot `from_warehouse`dan chiqim,
    `to_warehouse`ga kirim qilinadi. Tannarx o'zgarmaydi — ikkala harakat
    ham mahsulotning joriy o'rtacha tannarxi bilan yoziladi."""
    if transfer.status != StockTransfer.Status.DRAFT:
        raise ValidationError('Faqat DRAFT holatidagi kochirishni tasdiqlash mumkin.')
    if transfer.from_warehouse_id == transfer.to_warehouse_id:
        raise ValidationError("Qaysi ombordan va qaysi omborga — har xil bo'lishi kerak.")

    items = list(transfer.items.select_related('product').all())
    if not items:
        raise ValidationError('Kochirishda kamida bitta mahsulot bolishi kerak.')

    reference = _transfer_reference(transfer)
    for item in items:
        unit_cost = get_weighted_average_cost(item.product)
        common = dict(
            product=item.product, quantity=item.quantity, pieces=item.pieces,
            movement_type=StockMovement.MovementType.TRANSFER, unit_cost=unit_cost,
            reference=reference, date=transfer.date, created_by=user,
        )
        stock_out(warehouse=transfer.from_warehouse, **common)
        stock_in(warehouse=transfer.to_warehouse, **common)

    transfer.status = StockTransfer.Status.CONFIRMED
    transfer.save(update_fields=['status', 'updated_at'])
    return transfer


@transaction.atomic
def cancel_transfer(transfer: StockTransfer, *, user=None) -> StockTransfer:
    """Tasdiqlangan ko'chirishni bekor qiladi (mahsulot qaytib joyiga tushadi)."""
    if transfer.status != StockTransfer.Status.CONFIRMED:
        raise ValidationError('Faqat CONFIRMED holatidagi kochirishni bekor qilish mumkin.')
    for item in transfer.items.select_related('product'):
        available = get_stock(item.product, transfer.to_warehouse)
        if item.quantity > available:
            raise ValidationError(
                f"{transfer.to_warehouse.name}: {item.product.name} yetarli emas "
                f"(qoldiq: {available} kg) — ko'chirishni bekor qilib bo'lmaydi."
            )
    reverse_movements(reference=_transfer_reference(transfer), date=transfer.date, created_by=user)
    transfer.status = StockTransfer.Status.CANCELLED
    transfer.save(update_fields=['status', 'updated_at'])
    return transfer


def stock_fields_by_warehouse() -> callable:
    """Formalardagi mahsulot JSON'i uchun: har bir mahsulotga omborlar
    kesimidagi qoldiqni (`stock_by_wh`, `pieces_by_wh`) va asosiy ombor
    qoldig'ini (`stock`, `stock_pieces`) qaytaruvchi funksiya beradi. JS
    "Ombor" tanlovi o'zgarganda `stock`ni tegishli ombor qiymatiga almashtiradi."""
    warehouses = list(Warehouse.objects.filter(active=True))
    default_id = resolve_warehouse(None).id
    kg = {w.id: _stock_map('quantity', w) for w in warehouses}
    pcs = {w.id: _stock_map('pieces', w) for w in warehouses}

    def fields(product_id):
        return {
            'stock': str(kg.get(default_id, {}).get(product_id, 0)),
            'stock_pieces': pcs.get(default_id, {}).get(product_id, 0),
            'stock_by_wh': {str(w): str(m.get(product_id, 0)) for w, m in kg.items()},
            'pieces_by_wh': {str(w): m.get(product_id, 0) for w, m in pcs.items()},
        }
    return fields
