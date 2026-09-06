from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.common.date_filters import get_date_range
from apps.expenses.forms import ExpenseForm
from apps.expenses.models import Expense, ExpenseCategory
from apps.kassa.models import CashTransaction
from apps.kassa.services import cash_service


@login_required
def expense_list(request):
    expenses = Expense.objects.select_related('category').all()
    category_id = request.GET.get('category')
    date_from, date_to = get_date_range(request)
    if category_id:
        expenses = expenses.filter(category_id=category_id)
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)

    return render(request, 'expenses/list.html', {
        'expenses': expenses[:200],
        'categories': ExpenseCategory.objects.filter(active=True),
        'date_from': date_from,
        'date_to': date_to,
        'cash_balance': cash_service.get_balance(),
    })


@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            try:
                with transaction.atomic():
                    expense.save()
                    if expense.payment_type == Expense.PaymentType.CASH:
                        cash_service.record_cash_out(
                            amount=expense.amount, transaction_type=CashTransaction.TransactionType.EXPENSE,
                            date=expense.date, reference=f'EXPENSE:{expense.pk}', created_by=request.user,
                        )
                messages.success(request, "Xarajat qo'shildi.")
                return redirect('expenses:list')
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
    else:
        form = ExpenseForm(initial={'date': timezone.localdate()})
    return render(request, 'expenses/form.html', {
        'form': form,
        'cash_balance': cash_service.get_balance(),
    })
