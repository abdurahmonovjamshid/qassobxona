"""Payment (to'lov) uchun business logic."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.kassa.models import CashRegister, CashTransaction
from apps.kassa.services import cash_service
from apps.payments.models import Payment


def _reference(payment: Payment) -> str:
    return f'PAYMENT:{payment.pk}'


def _cash_transaction_type(payment: Payment) -> str:
    """Kassa yozuvining turi tomon (mijoz/yetkazib beruvchi) va yo'nalishdan
    kelib chiqadi. Odatdagi yo'nalish to'lov, teskarisi qaytarim deb yoziladi
    — shunda kassa tarixida yozuvning nomi ham ishorasiga mos keladi."""
    if payment.customer_id:
        return (CashTransaction.TransactionType.SALE_PAYMENT if payment.is_incoming
                else CashTransaction.TransactionType.SALE_REFUND)
    return (CashTransaction.TransactionType.PURCHASE_REFUND if payment.is_incoming
            else CashTransaction.TransactionType.PURCHASE_PAYMENT)


def _register(payment: Payment):
    """To'lov yozilgan kassa. Eski to'lovlarda `cash_register` bo'sh bo'lishi
    mumkin — ular uchun naqd to'lov Naqd kassada deb hisoblanadi."""
    if payment.cash_register_id:
        return payment.cash_register
    if payment.payment_type == Payment.PaymentType.CASH:
        return CashRegister.get_default()
    return None


def _notes(payment: Payment) -> str:
    """Kassa yozuviga to'lov izohi ham yoziladi — to'lov keyin o'chirilsa
    ham kassa tarixida izoh saqlanib qoladi."""
    return (payment.notes or '')[:255]


def apply_cash_effect(payment: Payment, *, user=None) -> None:
    register = _register(payment)
    if register is None:
        return
    if payment.is_incoming:
        cash_service.record_cash_in(
            amount=payment.amount, transaction_type=_cash_transaction_type(payment),
            date=payment.date, reference=_reference(payment), created_by=user, register=register,
            notes=_notes(payment),
        )
    else:
        cash_service.record_cash_out(
            amount=payment.amount, transaction_type=_cash_transaction_type(payment),
            date=payment.date, reference=_reference(payment), created_by=user, register=register,
            notes=_notes(payment),
        )


def _reverse_cash_effect(payment: Payment, *, user=None) -> None:
    register = _register(payment)
    if register is None:
        return
    if payment.is_incoming:
        # Kassaga kirim bo'lgan to'lov o'chirilyapti — endi teskarisi (chiqim)
        # yoziladi. Balans yetarli bo'lmasa ham amalga oshadi (bu tuzatish,
        # yangi xarajat emas).
        cash_service.record_cash_out(
            amount=payment.amount, transaction_type=CashTransaction.TransactionType.ADJUSTMENT,
            date=payment.date, reference=f'REVERSE:{_reference(payment)}', created_by=user, notes=_notes(payment),
            enforce_balance=False, register=register,
        )
    else:
        cash_service.record_cash_in(
            amount=payment.amount, transaction_type=CashTransaction.TransactionType.ADJUSTMENT,
            date=payment.date, reference=f'REVERSE:{_reference(payment)}', created_by=user, notes=_notes(payment),
            register=register,
        )


def default_direction(*, customer=None, supplier=None) -> str:
    """Odatdagi yo'nalish: mijozdan pul olamiz, yetkazib beruvchiga to'laymiz.
    Chaqiruvchi yo'nalishni ko'rsatmasa shu ishlatiladi."""
    return Payment.Direction.OUT if supplier else Payment.Direction.IN


@transaction.atomic
def create_payment(*, amount, date, payment_type=None, cash_register=None, customer=None, supplier=None,
                    sale=None, purchase=None, notes='', user=None, direction=None) -> Payment:
    """To'lov yaratadi, tegishli Sale/Purchase qarzini qayta hisoblaydi va
    tanlangan kassa balansini yangilaydi.

    `cash_register` berilsa to'lov turi shu kassadan olinadi (Naqd kassa ->
    CASH, Karta kassa -> CARD). Faqat `payment_type` berilsa kassa undan
    topiladi (CASH/CARD); o'tkazma va boshqa turlar kassaga yozilmaydi.
    Ikkalasi ham berilmasa — Naqd kassa."""
    if cash_register is not None:
        payment_type = cash_register.code
    elif payment_type:
        cash_register = CashRegister.for_payment_type(payment_type)
    else:
        cash_register = CashRegister.get_default()
        payment_type = cash_register.code
    if amount is None or amount <= 0:
        raise ValidationError('Tolov summasi musbat bolishi kerak.')
    if customer and supplier:
        raise ValidationError('Tolov bir vaqtda customer va supplierga tegishli bolmasin.')
    if not customer and not supplier:
        raise ValidationError('Tolov customer yoki supplierga boglanishi kerak.')

    if direction is None:
        direction = default_direction(customer=customer, supplier=supplier)
    if direction not in Payment.Direction.values:
        raise ValidationError("Tolov yonalishi notogri.")

    payment = Payment.objects.create(
        amount=amount,
        direction=direction,
        payment_type=payment_type,
        cash_register=cash_register,
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
