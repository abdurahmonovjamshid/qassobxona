from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.common.date_filters import get_date_range
from apps.kassa.forms import CashBalanceAdjustmentForm
from apps.kassa.models import CashTransaction
from apps.kassa.services import cash_service


@login_required
def kassa_detail(request):
    transactions = CashTransaction.objects.select_related('created_by').all()
    date_from, date_to = get_date_range(request)
    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)

    return render(request, 'kassa/detail.html', {
        'balance': cash_service.get_balance(),
        'transactions': transactions[:200],
        'date_from': date_from,
        'date_to': date_to,
        'balance_form': CashBalanceAdjustmentForm(initial={'date': timezone.localdate()}),
    })


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
                )
                messages.success(request, "Kassa balansi yangilandi.")
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
        else:
            messages.error(request, "Ma'lumotlarni tekshiring.")
    return redirect('kassa:detail')
