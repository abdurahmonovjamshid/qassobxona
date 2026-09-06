from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from apps.common.date_filters import get_date_range
from apps.common.excel_export import statement_to_response
from apps.purchases.models import Purchase
from apps.reports.services import statement_service
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
        total_purchases = supplier.get_total_purchases()
        total_debt = supplier.get_total_debt()
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
    return render(request, 'suppliers/form.html', {'form': form, 'title': 'Yangi yetkazib beruvchi'})


@login_required
def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, f"{supplier.name} yangilandi.")
            return redirect('suppliers:detail', pk=supplier.pk)
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'suppliers/form.html', {'form': form, 'title': supplier.name})


@login_required
def supplier_statement(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    date_from, date_to = get_date_range(request)
    statement = statement_service.build_partner_statement_for_supplier(
        supplier, date_from=parse_date(date_from) if date_from else None,
        date_to=parse_date(date_to) if date_to else None,
    )
    return render(request, 'suppliers/statement.html', {
        'supplier': supplier,
        'statement': statement,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
def supplier_statement_export(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    date_from, date_to = get_date_range(request)
    statement = statement_service.build_partner_statement_for_supplier(
        supplier, date_from=parse_date(date_from) if date_from else None,
        date_to=parse_date(date_to) if date_to else None,
    )
    sections = [('Yetkazib beruvchi (xarid)', statement['supplier_statement'])]
    if statement['customer_statement']:
        sections.insert(0, ('Mijoz (sotuv)', statement['customer_statement']))
    return statement_to_response(filename=f'akt-sverka-{supplier.name}.xlsx', sections=sections)


@login_required
def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    purchases = supplier.purchases.exclude(status=Purchase.Status.CANCELLED)
    payments = supplier.payments.all()

    total_purchases = supplier.get_total_purchases()
    total_payments = supplier.get_total_payments()
    debt = supplier.get_total_debt()

    history = []
    if supplier.opening_balance:
        history.append({
            'date': supplier.created_at.date(), 'op': "Boshlang'ich qarz",
            'amount': supplier.opening_balance, 'kind': 'opening',
        })
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
