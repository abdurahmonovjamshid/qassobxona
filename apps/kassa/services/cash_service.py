"""Kassa (naqd pul) uchun business logic. Har bir naqd harakat (sotuv/xarid
to'lovi, xarajat) shu servis orqali yoziladi. Balans qo'lda o'zgartirilmaydi —
faqat Django admin panel orqali ADJUSTMENT yozuvi qo'shish mumkin
(apps/kassa/admin.py), bu esa "kassa balansini faqat admin o'zgartira oladi"
talabini ta'minlaydi."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from apps.kassa.models import CashTransaction


def get_balance() -> Decimal:
    return CashTransaction.objects.aggregate(s=Sum('amount'))['s'] or Decimal('0')


def _create(*, amount, transaction_type, date, reference='', notes='', created_by=None) -> CashTransaction:
    return CashTransaction.objects.create(
        amount=amount, transaction_type=transaction_type, date=date,
        reference=reference, notes=notes, created_by=created_by,
    )


def record_cash_in(*, amount, transaction_type, date, reference='', notes='', created_by=None) -> CashTransaction:
    if amount is None or amount <= 0:
        raise ValidationError('Kassa kirim summasi musbat bolishi kerak.')
    return _create(
        amount=amount, transaction_type=transaction_type, date=date,
        reference=reference, notes=notes, created_by=created_by,
    )


def record_manual_balance(*, amount, date, notes='', created_by=None) -> CashTransaction:
    """Superuser tomonidan kassa balansiga qo'lda naqd pul kiritish (masalan
    dasturdan foydalanishni boshlaganda mavjud naqd qoldiqni belgilash uchun).
    `amount` musbat bo'lsa kirim, manfiy bo'lsa chiqim sifatida yoziladi.
    Bu yagona joy — bundan tashqari kassa faqat Sale/Purchase to'lovlari va
    xarajatlar orqali avtomatik yoziladi."""
    if amount is None or amount == 0:
        raise ValidationError('Summa nolga teng bolmasligi kerak.')
    return _create(
        amount=amount, transaction_type=CashTransaction.TransactionType.OPENING,
        date=date, notes=notes, created_by=created_by,
    )


def record_cash_out(*, amount, transaction_type, date, reference='', notes='', created_by=None,
                     enforce_balance=True) -> CashTransaction:
    if amount is None or amount <= 0:
        raise ValidationError('Kassa chiqim summasi musbat bolishi kerak.')
    if enforce_balance:
        balance = get_balance()
        if amount > balance:
            raise ValidationError(
                f"Kassada yetarli mablag' yo'q. Joriy balans: {balance} so'm, "
                f"talab qilingan: {amount} so'm."
            )
    return _create(
        amount=-amount, transaction_type=transaction_type, date=date,
        reference=reference, notes=notes, created_by=created_by,
    )
