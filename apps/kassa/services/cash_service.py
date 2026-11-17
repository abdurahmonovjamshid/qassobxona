"""Kassa (naqd pul) uchun business logic. Har bir naqd harakat (sotuv/xarid
to'lovi, xarajat) shu servis orqali yoziladi. Balans qo'lda o'zgartirilmaydi —
faqat Django admin panel orqali ADJUSTMENT yozuvi qo'shish mumkin
(apps/kassa/admin.py), bu esa "kassa balansini faqat admin o'zgartira oladi"
talabini ta'minlaydi."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from apps.kassa.models import CashRegister, CashTransaction


def resolve_register(register) -> CashRegister:
    """`None` berilsa asosiy (Naqd) kassa."""
    return register or CashRegister.get_default()


def get_balance(register=None) -> Decimal:
    """Kassa balansi. `register` berilmasa — asosiy (Naqd) kassa."""
    register = resolve_register(register)
    return CashTransaction.objects.filter(register=register).aggregate(s=Sum('amount'))['s'] or Decimal('0')


def get_balances() -> list:
    """Har bir kassa balansi: [{'register', 'balance'}, ...] (Naqd birinchi)."""
    CashRegister.get_default()
    return [{'register': r, 'balance': get_balance(r)} for r in CashRegister.objects.all()]


def _create(*, amount, transaction_type, date, reference='', notes='', created_by=None,
            register=None) -> CashTransaction:
    return CashTransaction.objects.create(
        register=resolve_register(register),
        amount=amount, transaction_type=transaction_type, date=date,
        reference=reference, notes=notes, created_by=created_by,
    )


def record_cash_in(*, amount, transaction_type, date, reference='', notes='', created_by=None,
                   register=None) -> CashTransaction:
    if amount is None or amount <= 0:
        raise ValidationError('Kassa kirim summasi musbat bolishi kerak.')
    return _create(
        amount=amount, transaction_type=transaction_type, date=date,
        reference=reference, notes=notes, created_by=created_by, register=register,
    )


def record_manual_balance(*, amount, date, notes='', created_by=None, register=None) -> CashTransaction:
    """Superuser tomonidan kassa balansiga qo'lda pul kiritish (masalan
    dasturdan foydalanishni boshlaganda mavjud qoldiqni belgilash uchun).
    `amount` musbat bo'lsa kirim, manfiy bo'lsa chiqim sifatida yoziladi.
    Bu yagona joy — bundan tashqari kassa faqat Sale/Purchase to'lovlari va
    xarajatlar orqali avtomatik yoziladi."""
    if amount is None or amount == 0:
        raise ValidationError('Summa nolga teng bolmasligi kerak.')
    return _create(
        amount=amount, transaction_type=CashTransaction.TransactionType.OPENING,
        date=date, notes=notes, created_by=created_by, register=register,
    )


def record_cash_out(*, amount, transaction_type, date, reference='', notes='', created_by=None,
                    enforce_balance=True, register=None) -> CashTransaction:
    if amount is None or amount <= 0:
        raise ValidationError('Kassa chiqim summasi musbat bolishi kerak.')
    register = resolve_register(register)
    if enforce_balance:
        balance = get_balance(register)
        if amount > balance:
            raise ValidationError(
                f"{register.name}da yetarli mablag' yo'q. Joriy balans: {balance} so'm, "
                f"talab qilingan: {amount} so'm."
            )
    return _create(
        amount=-amount, transaction_type=transaction_type, date=date,
        reference=reference, notes=notes, created_by=created_by, register=register,
    )


def attach_document_info(transactions) -> list:
    """Kassa yozuvlariga havola qilingan hujjatning izohi (`doc_notes`) va
    kontragentini (`party`) qo'shadi. Kassa yozuvining o'z `notes`i faqat
    qo'lda kiritilgan yozuvlarda bo'ladi, to'lov/xarajat/bo'laklash izohi esa
    hujjatning o'zida saqlanadi — shu yerda `reference` bo'yicha topiladi
    (bekor qilish yozuvlari `REVERSE:` prefiksi bilan ham ishlaydi)."""
    from apps.butchering.models import Butchering
    from apps.expenses.models import Expense
    from apps.payments.models import Payment

    transactions = list(transactions)
    ids = {'PAYMENT': set(), 'EXPENSE': set(), 'BUTCHERING': set()}

    def parse(reference):
        parts = (reference or '').removeprefix('REVERSE:').split(':')
        if len(parts) == 2 and parts[0] in ids and parts[1].isdigit():
            return parts[0], int(parts[1])
        return None, None

    for t in transactions:
        kind, pk = parse(t.reference)
        if kind:
            ids[kind].add(pk)

    payments = Payment.objects.select_related('customer', 'supplier').in_bulk(ids['PAYMENT'])
    expenses = Expense.objects.select_related('category').in_bulk(ids['EXPENSE'])
    butcherings = Butchering.objects.select_related('input_product').in_bulk(ids['BUTCHERING'])

    for t in transactions:
        kind, pk = parse(t.reference)
        notes, party = '', ''
        if kind == 'PAYMENT' and pk in payments:
            payment = payments[pk]
            notes = payment.notes
            party = (payment.customer or payment.supplier).name if (payment.customer or payment.supplier) else ''
        elif kind == 'EXPENSE' and pk in expenses:
            notes = expenses[pk].description
            party = expenses[pk].category.name
        elif kind == 'BUTCHERING' and pk in butcherings:
            notes = butcherings[pk].notes
            party = f"Bo'laklash: {butcherings[pk].input_product.name}"
        # Yangi yozuvlarda izoh kassa yozuvining o'zida ham bor — takrorlanmasin.
        t.doc_notes = ' · '.join(dict.fromkeys(filter(None, [t.notes, notes])))
        t.party = party
    return transactions
