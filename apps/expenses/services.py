"""Xarajat (Expense) yaratish — web (`expenses/views.py`) va bot
(`bot/handlers/expenses.py`) bir xil yo'l bilan ishlashi uchun."""
from django.db import transaction

from apps.expenses.models import Expense
from apps.kassa.models import CashRegister, CashTransaction
from apps.kassa.services import cash_service


@transaction.atomic
def create_expense(*, category, amount, date, description='', cash_register=None, user=None) -> Expense:
    """Xarajatni saqlaydi va tanlangan kassadan (bo'sh bo'lsa Naqd kassa)
    chiqim qiladi. Kassada mablag' yetmasa ValidationError — hech narsa
    saqlanmaydi."""
    register = cash_service.resolve_register(cash_register)
    expense = Expense.objects.create(
        category=category, amount=amount, date=date, description=description,
        payment_type=register.code, cash_register=register, created_by=user,
    )
    cash_service.record_cash_out(
        amount=expense.amount, transaction_type=CashTransaction.TransactionType.EXPENSE,
        date=expense.date, reference=f'EXPENSE:{expense.pk}', created_by=user, register=register,
        notes=(description or '')[:255],
    )
    return expense


def register_choices():
    CashRegister.get_default()
    return CashRegister.objects.all()
