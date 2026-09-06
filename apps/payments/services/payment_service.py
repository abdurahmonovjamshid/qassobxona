"""Payment (to'lov) uchun business logic."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.kassa.models import CashTransaction
from apps.kassa.services import cash_service
from apps.payments.models import Payment


def _reference(payment: Payment) -> str:
    return f'PAYMENT:{payment.pk}'


def apply_cash_effect(payment: Payment, *, user=None) -> None:
    if payment.payment_type != Payment.PaymentType.CASH:
        return
    if payment.customer_id:
        cash_service.record_cash_in(
            amount=payment.amount, transaction_type=CashTransaction.TransactionType.SALE_PAYMENT,
            date=payment.date, reference=_reference(payment), created_by=user,
        )
    else:
        cash_service.record_cash_out(
            amount=payment.amount, transaction_type=CashTransaction.TransactionType.PURCHASE_PAYMENT,
            date=payment.date, reference=_reference(payment), created_by=user,
        )


def _reverse_cash_effect(payment: Payment, *, user=None) -> None:
    if payment.payment_type != Payment.PaymentType.CASH:
        return
    if payment.customer_id:
        # Mijozdan olingan naqd to'lov o'chirilyapti — bu avval kassaga kirim
        # bo'lgan edi, endi teskarisi (chiqim) yoziladi. Balans yetarli
        # bo'lmasa ham amalga oshadi (bu tuzatish, yangi xarajat emas).
        cash_service.record_cash_out(
            amount=payment.amount, transaction_type=CashTransaction.TransactionType.ADJUSTMENT,
            date=payment.date, reference=f'REVERSE:{_reference(payment)}', created_by=user,
            enforce_balance=False,
        )
    else:
        cash_service.record_cash_in(
            amount=payment.amount, transaction_type=CashTransaction.TransactionType.ADJUSTMENT,
            date=payment.date, reference=f'REVERSE:{_reference(payment)}', created_by=user,
        )


@transaction.atomic
def create_payment(*, amount, payment_type, date, customer=None, supplier=None,
                    sale=None, purchase=None, notes='', user=None) -> Payment:
    """To'lov yaratadi, tegishli Sale/Purchase qarzini qayta hisoblaydi va
    (naqd bo'lsa) kassa balansini yangilaydi."""
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
    apply_cash_effect(payment, user=user)
    return payment


@transaction.atomic
def delete_payment(payment: Payment, *, user=None) -> None:
    """To'lovni o'chiradi, tegishli Sale/Purchase qarzini qayta hisoblaydi va
    (naqd bo'lsa) kassa balansini teskari tuzatadi."""
    sale = payment.sale
    purchase = payment.purchase
    _reverse_cash_effect(payment, user=user)
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
