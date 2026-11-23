from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.common.date_filters import get_date_range
from apps.common.excel_export import table_to_response
from apps.kassa.forms import CashBalanceAdjustmentForm
from apps.kassa.models import CashRegister, CashTransaction
from apps.kassa.services import cash_service


def _filtered_transactions(request):
    transactions = CashTransaction.objects.select_related('created_by', 'register').all()
    register = CashRegister.objects.filter(pk=request.GET.get('register') or None).first()
    if register:
        transactions = transactions.filter(register=register)
    date_from, date_to = get_date_range(request)
    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)
    return transactions, register, date_from, date_to


@login_required
def kassa_detail(request):
    transactions, register, date_from, date_to = _filtered_transactions(request)
    return render(request, 'kassa/detail.html', {
        'balances': cash_service.get_balances(),
        'registers': CashRegister.objects.all(),
        'register': register,
        'transactions': cash_service.attach_document_info(transactions[:200]),
        'date_from': date_from,
        'date_to': date_to,
        'balance_form': CashBalanceAdjustmentForm(initial={'date': timezone.localdate()}),
    })


@login_required
def kassa_export(request):
    """Kassa harakatlarini (sahifadagi filtrlar bilan, cheklovsiz) Excelga."""
    transactions, register, _, _ = _filtered_transactions(request)
    headers = ['Sana', 'Kassa', 'Turi', 'Mijoz / Yetkazib beruvchi', 'Kim', 'Tafsilot',
               'Kirim', 'Chiqim', 'Havola', 'Izoh']
    rows = []
    for t in cash_service.attach_document_info(transactions):
        rows.append([
            t.date.strftime('%d.%m.%Y'), t.register.name, t.get_transaction_type_display(),
            t.counterparty, t.counterparty_kind, t.party,
            float(t.amount) if t.amount > 0 else None,
            float(-t.amount) if t.amount < 0 else None,
            t.reference, t.doc_notes,
        ])
    prefix = 'kassa' if register is None else f'kassa_{register.code.lower()}'
    return table_to_response(filename_prefix=prefix, headers=headers, rows=rows, sheet_title='Kassa')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def kassa_add_balance(request):
    """Kassa balansiga qo'lda naqd pul kiritish (masalan dasturdan
    foydalanishni boshlaganda mavjud naqd qoldiqni belgilash uchun).
    Faqat superuser uchun — kassa balansini qo'lda o'zgartirish shu yerda
    yoki Django admin orqaligina mumkin, boshqa sahifalar uni faqat o'qiydi."""
    if request.method == 'POST':
        form = CashBalanceAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                cash_service.record_manual_balance(
                    amount=form.cleaned_data['amount'], date=form.cleaned_data['date'],
                    notes=form.cleaned_data.get('notes', ''), created_by=request.user,
                    register=form.cleaned_data.get('cash_register'),
                )
                messages.success(request, "Kassa balansi yangilandi.")
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
        else:
            messages.error(request, "Ma'lumotlarni tekshiring.")
    return redirect('kassa:detail')
