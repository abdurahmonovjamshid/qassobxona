from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.purchases.models import Purchase
from apps.suppliers.forms import SupplierForm
from apps.suppliers.models import Supplier


@login_required
def supplier_list(request):
    suppliers = Supplier.objects.all()
    q = request.GET.get('q')
    if q:
        suppliers = suppliers.filter(name__icontains=q)

    rows = []
    for supplier in suppliers:
        total_purchases = supplier.purchases.filter(status=Purchase.Status.CONFIRMED).aggregate(
            s=Sum('total_amount'))['s'] or Decimal('0')
        total_debt = supplier.purchases.filter(status=Purchase.Status.CONFIRMED).aggregate(
            s=Sum('debt_amount'))['s'] or Decimal('0')
        rows.append({'supplier': supplier, 'total_purchases': total_purchases, 'debt': total_debt})

    return render(request, 'suppliers/list.html', {'rows': rows})


@login_required
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f"{supplier.name} qo'shildi.")
            return redirect('suppliers:detail', pk=supplier.pk)
    else:
        form = SupplierForm()
    return render(request, 'suppliers/form.html', {'form': form})


@login_required
def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    purchases = supplier.purchases.exclude(status=Purchase.Status.CANCELLED)
    payments = supplier.payments.all()

    total_purchases = purchases.filter(status=Purchase.Status.CONFIRMED).aggregate(
        s=Sum('total_amount'))['s'] or Decimal('0')
    total_payments = payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    debt = purchases.filter(status=Purchase.Status.CONFIRMED).aggregate(s=Sum('debt_amount'))['s'] or Decimal('0')

    history = []
    for purchase in purchases:
        history.append({'date': purchase.date, 'op': f'Xarid {purchase.purchase_number}', 'amount': purchase.total_amount, 'kind': 'purchase'})
    for payment in payments:
        history.append({'date': payment.date, 'op': "To'lov", 'amount': payment.amount, 'kind': 'payment'})
    history.sort(key=lambda h: h['date'])

    return render(request, 'suppliers/detail.html', {
        'supplier': supplier,
        'total_purchases': total_purchases,
        'total_payments': total_payments,
        'debt': debt,
        'history': history,
    })
