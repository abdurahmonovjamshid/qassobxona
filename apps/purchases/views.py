import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.payments.services import payment_service
from apps.products.models import Product
from apps.purchases.forms import PurchaseExpenseFormSet, PurchaseForm
from apps.purchases.models import Purchase
from apps.purchases.services import purchase_service


def _products_json():
    products = Product.objects.filter(active=True).order_by('name')
    return json.dumps([
        {'id': p.id, 'name': p.name, 'unit': p.unit, 'image': p.image.url if p.image else None}
        for p in products
    ])


def _generate_purchase_number():
    today = timezone.localdate()
    prefix = f"P{today.strftime('%Y%m%d')}"
    last = Purchase.objects.filter(purchase_number__startswith=prefix).order_by('-purchase_number').first()
    seq = int(last.purchase_number.rsplit('-', 1)[-1]) + 1 if last else 1
    return f"{prefix}-{seq:04d}"


@login_required
def purchase_list(request):
    purchases = Purchase.objects.select_related('supplier', 'product').all()

    supplier_id = request.GET.get('supplier')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if supplier_id:
        purchases = purchases.filter(supplier_id=supplier_id)
    if status:
        purchases = purchases.filter(status=status)
    if date_from:
        purchases = purchases.filter(date__gte=date_from)
    if date_to:
        purchases = purchases.filter(date__lte=date_to)

    return render(request, 'purchases/list.html', {
        'purchases': purchases[:200],
        'statuses': Purchase.Status.choices,
    })


@login_required
def purchase_create(request):
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        if form.is_valid():
            purchase = form.save(commit=False)
            formset = PurchaseExpenseFormSet(request.POST, instance=purchase)
            if formset.is_valid():
                try:
                    with transaction.atomic():
                        purchase.purchase_number = _generate_purchase_number()
                        purchase.status = Purchase.Status.DRAFT
                        purchase.paid_amount = Decimal('0')
                        purchase.save()
                        formset.instance = purchase
                        formset.save()

                        purchase_service.confirm_purchase(purchase, user=request.user)

                        paid_amount = form.cleaned_data.get('paid_amount') or Decimal('0')
                        if paid_amount > 0:
                            payment_service.create_payment(
                                amount=paid_amount, payment_type='CASH', date=purchase.date,
                                supplier=purchase.supplier, purchase=purchase, user=request.user,
                            )
                    messages.success(request, f"Xarid {purchase.purchase_number} muvaffaqiyatli tasdiqlandi.")
                    return redirect('purchases:detail', pk=purchase.pk)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
        else:
            formset = PurchaseExpenseFormSet(request.POST)
    else:
        form = PurchaseForm(initial={'date': timezone.localdate()})
        formset = PurchaseExpenseFormSet()

    return render(request, 'purchases/form.html', {
        'form': form, 'formset': formset, 'products_json': _products_json(),
    })


@login_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'product'), pk=pk)
    return render(request, 'purchases/detail.html', {
        'purchase': purchase,
        'expenses': purchase.extra_expenses.all(),
        'payments': purchase.payments.all(),
        'butcherings': purchase.butcherings.all(),
    })


@login_required
def purchase_cancel(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == 'POST':
        try:
            purchase_service.cancel_purchase(purchase, user=request.user)
            messages.success(request, f"Xarid {purchase.purchase_number} bekor qilindi.")
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return redirect('purchases:detail', pk=pk)
