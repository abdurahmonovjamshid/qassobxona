from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.common.date_filters import get_date_range
from apps.common.excel_export import table_to_response
from apps.expenses.forms import ExpenseForm
from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses import services as expense_services
from apps.kassa.services import cash_service


def _filtered_expenses(request):
    expenses = Expense.objects.select_related('category', 'cash_register').all()
    category_id = request.GET.get('category')
    date_from, date_to = get_date_range(request)
    if category_id:
        expenses = expenses.filter(category_id=category_id)
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
    return expenses, date_from, date_to


@login_required
def expense_list(request):
    expenses, date_from, date_to = _filtered_expenses(request)
    return render(request, 'expenses/list.html', {
        'expenses': expenses[:200],
        'categories': ExpenseCategory.objects.filter(active=True),
        'date_from': date_from,
        'date_to': date_to,
        'balances': cash_service.get_balances(),
    })


@login_required
def expense_export(request):
    """Xarajatlarni (sahifadagi filtrlar bilan, cheklovsiz) Excelga."""
    expenses, _, _ = _filtered_expenses(request)
    headers = ['Sana', 'Kategoriya', 'Kassa', 'Izoh', 'Summa']
    rows = [
        [e.date.strftime('%d.%m.%Y'), e.category.name,
         e.cash_register.name if e.cash_register_id else e.get_payment_type_display(),
         e.description, float(e.amount)]
        for e in expenses
    ]
    rows.append(['', '', '', 'Jami', float(sum(e.amount for e in expenses))])
    return table_to_response(filename_prefix='xarajatlar', headers=headers, rows=rows, sheet_title='Xarajatlar')


@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                expense_services.create_expense(
                    category=data['category'], amount=data['amount'], date=data['date'],
                    description=data.get('description', ''), cash_register=data.get('cash_register'),
                    user=request.user,
                )
                messages.success(request, "Xarajat qo'shildi.")
                return redirect('expenses:list')
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
    else:
        form = ExpenseForm(initial={'date': timezone.localdate()})
    return render(request, 'expenses/form.html', {
        'form': form,
        'balances': cash_service.get_balances(),
    })
