from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.common.date_filters import get_date_range
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
    })
