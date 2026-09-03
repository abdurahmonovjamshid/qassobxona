"""Payment (to'lov) uchun business logic."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.payments.models import Payment


@transaction.atomic
def create_payment(*, amount, payment_type, date, customer=None, supplier=None,
                    sale=None, purchase=None, notes='', user=None) -> Payment:
    """To'lov yaratadi va tegishli Sale/Purchase qarzini qayta hisoblaydi."""
    if amount is None or amount <= 0:
        raise ValidationError('Tolov summasi musbat bolishi kerak.')
    if customer and supplier:
        raise ValidationError('Tolov bir vaqtda customer va supplierga tegishli bolmasin.')
    if not customer and not supplier:
        raise ValidationError('Tolov customer yoki supplierga boglanishi kerak.')

    payment = Payment.objects.create(
        amount=amount,
        payment_type=payment_type,
        date=date,
        customer=customer,
        supplier=supplier,
        sale=sale,
        purchase=purchase,
        notes=notes,
        created_by=user,
    )

    _recalc_related(payment)
    return payment


@transaction.atomic
def delete_payment(payment: Payment) -> None:
    """To'lovni o'chiradi va tegishli Sale/Purchase qarzini qayta hisoblaydi."""
    sale = payment.sale
    purchase = payment.purchase
    payment.delete()
    if sale is not None:
        from apps.sales.services import sale_service
        sale_service.recalc_sale_payment(sale)
    if purchase is not None:
        from apps.purchases.services import purchase_service
        purchase_service.recalc_purchase_payment(purchase)


def _recalc_related(payment: Payment) -> None:
    if payment.sale_id:
        from apps.sales.services import sale_service
        sale_service.recalc_sale_payment(payment.sale)
    if payment.purchase_id:
        from apps.purchases.services import purchase_service
        purchase_service.recalc_purchase_payment(payment.purchase)
