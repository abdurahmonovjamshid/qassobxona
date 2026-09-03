"""Butchering (bo'laklash) uchun business logic."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.butchering.models import Butchering
from apps.inventory.models import StockMovement
from apps.inventory.services import inventory_service


def _reference(butchering: Butchering) -> str:
    return f'BUTCHERING:{butchering.pk}'


@transaction.atomic
def confirm_butchering(butchering: Butchering, *, user=None) -> Butchering:
    """Bo'laklashni tasdiqlaydi: input mahsulot ombordan chiqadi,
    output mahsulotlar omborga kiradi, yield/difference hisoblanadi."""
    if butchering.status != Butchering.Status.DRAFT:
        raise ValidationError('Faqat DRAFT holatidagi bolaklashni tasdiqlash mumkin.')

    outputs = list(butchering.outputs.select_related('product').all())
    if not outputs:
        raise ValidationError('Bolaklashda kamida bitta output mahsulot bolishi kerak.')

    output_total = sum((o.quantity for o in outputs), Decimal('0'))
    if output_total > butchering.input_weight:
        raise ValidationError('Output inputdan katta bolmasligi kerak.')

    reference = _reference(butchering)

    # 1) input mahsulot ombordan chiqadi
    input_unit_cost = inventory_service.get_weighted_average_cost(butchering.input_product)
    inventory_service.stock_out(
        product=butchering.input_product,
        quantity=butchering.input_weight,
        movement_type=StockMovement.MovementType.BUTCHERING_OUT,
        unit_cost=input_unit_cost,
        reference=reference,
        date=butchering.date,
        created_by=user,
    )

    # 2) tannarx output'larga QIYMAT (sotuv narxi) ulushi boyicha taqsimlanadi
    #    (og'irlik ulushi emas) — aks holda suyak/yog'/chiqit kabi arzon
    #    mahsulotlarga lahm bilan bir xil tannarx tegib, ular sun'iy ravishda
    #    "zararda" ko'rinib qoladi. Qaysidir mahsulotning sotuv narxi 0
    #    bolsa, shu mahsulot uchun og'irlik ulushiga qaytiladi.
    total_input_cost = input_unit_cost * butchering.input_weight
    total_value = sum((o.quantity * o.product.sale_price for o in outputs), Decimal('0'))
    for output in outputs:
        if total_value > 0:
            output_value = output.quantity * output.product.sale_price
            share = output_value / total_value
        else:
            share = (output.quantity / output_total) if output_total > 0 else Decimal('0')
        allocated_cost = total_input_cost * share
        unit_cost = (allocated_cost / output.quantity) if output.quantity > 0 else Decimal('0')
        output.unit_cost = unit_cost.quantize(Decimal('0.01'))
        output.save(update_fields=['unit_cost'])

        inventory_service.stock_in(
            product=output.product,
            quantity=output.quantity,
            movement_type=StockMovement.MovementType.BUTCHERING_IN,
            unit_cost=output.unit_cost,
            reference=reference,
            date=butchering.date,
            created_by=user,
        )

    butchering.output_weight = output_total
    butchering.difference = butchering.input_weight - output_total
    butchering.yield_percentage = (
        (output_total / butchering.input_weight) * Decimal('100')
        if butchering.input_weight else Decimal('0')
    ).quantize(Decimal('0.01'))
    butchering.status = Butchering.Status.CONFIRMED
    butchering.save()
    return butchering


@transaction.atomic
def cancel_butchering(butchering: Butchering, *, user=None) -> Butchering:
    """Tasdiqlangan bolaklashni bekor qiladi va ombor harakatlarini teskari qaytaradi."""
    if butchering.status != Butchering.Status.CONFIRMED:
        raise ValidationError('Faqat CONFIRMED holatidagi bolaklashni bekor qilish mumkin.')

    inventory_service.reverse_movements(
        reference=_reference(butchering),
        date=butchering.date,
        created_by=user,
    )

    butchering.status = Butchering.Status.CANCELLED
    butchering.save(update_fields=['status', 'updated_at'])
    return butchering
