import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.common.date_filters import get_date_range
from apps.payments.services import payment_service
from apps.products.models import Product
from apps.purchases.forms import PurchaseExpenseFormSet, PurchaseForm, PurchaseItemFormSet
from apps.purchases.models import Purchase
from apps.purchases.services import purchase_service


def _products_json():
    products = Product.objects.filter(active=True).select_related('category').order_by('name')
    return json.dumps([
        {
            'id': p.id, 'name': p.name, 'unit': p.unit,
            'image': p.image.url if p.image else None,
            'category': p.category.code, 'category_label': p.category.name,
        }
        for p in products
    ])


def _cart_json_from_formset(formset):
    """Validatsiya xatosidan keyin formani qayta ko'rsatishda savatchani
    tiklash uchun — bog'langan formset qatorlaridan mahsulot/vazn/narx
    o'qib, JS kutgan shaklga o'giradi."""
    rows = []
    for f in formset.forms:
        product_id = f['product'].value()
        if not product_id:
            continue
        rows.append({
            'product_id': product_id,
            'net_weight': f['net_weight'].value() or '0',
            'pieces': f['pieces'].value() or '0',
            'price_per_kg': f['price_per_kg'].value() or '0',
        })
    if not rows:
        return '[]'

    products = Product.objects.in_bulk([r['product_id'] for r in rows])
    cart = []
    for r in rows:
        product = products.get(int(r['product_id']))
        if not product:
            continue
        cart.append({
            'id': product.id,
            'name': product.name,
            'unit': product.unit,
            'image': product.image.url if product.image else None,
            'net_weight': r['net_weight'],
            'pieces': r['pieces'],
            'price_per_kg': r['price_per_kg'],
        })
    return json.dumps(cart)


_generate_purchase_number = purchase_service.generate_purchase_number


@login_required
def purchase_list(request):
    purchases = Purchase.objects.select_related('supplier').prefetch_related('items').all()

    supplier_id = request.GET.get('supplier')
    status = request.GET.get('status')
    date_from, date_to = get_date_range(request)

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
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
def purchase_create(request):
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        if form.is_valid():
            purchase = form.save(commit=False)
            item_formset = PurchaseItemFormSet(request.POST, instance=purchase, prefix='items')
            expense_formset = PurchaseExpenseFormSet(request.POST, instance=purchase, prefix='expenses')
            if item_formset.is_valid() and expense_formset.is_valid():
                try:
                    with transaction.atomic():
                        purchase.purchase_number = _generate_purchase_number()
                        purchase.status = Purchase.Status.DRAFT
                        purchase.paid_amount = Decimal('0')
                        purchase.save()
                        item_formset.instance = purchase
                        item_formset.save()
                        expense_formset.instance = purchase
                        expense_formset.save()

                        purchase_service.confirm_purchase(purchase, user=request.user)

                        paid_amount = form.cleaned_data.get('paid_amount') or Decimal('0')
                        if paid_amount > 0:
                            payment_service.create_payment(
                                amount=paid_amount,
                                payment_type=form.cleaned_data.get('payment_type') or 'CASH',
                                date=purchase.date, supplier=purchase.supplier, purchase=purchase,
                                user=request.user,
                            )
                    messages.success(request, f"Xarid {purchase.purchase_number} muvaffaqiyatli tasdiqlandi.")
                    return redirect('purchases:detail', pk=purchase.pk)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
        else:
            item_formset = PurchaseItemFormSet(request.POST, prefix='items')
            expense_formset = PurchaseExpenseFormSet(request.POST, prefix='expenses')
        initial_cart_json = _cart_json_from_formset(item_formset)
    else:
        form = PurchaseForm(initial={'date': timezone.localdate()})
        item_formset = PurchaseItemFormSet(prefix='items')
        expense_formset = PurchaseExpenseFormSet(prefix='expenses')
        initial_cart_json = '[]'

    return render(request, 'purchases/form.html', {
        'form': form, 'item_formset': item_formset, 'expense_formset': expense_formset,
        'products_json': _products_json(),
        'initial_cart_json': initial_cart_json,
    })


@login_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase.objects.select_related('supplier').prefetch_related('items__product'), pk=pk)
    return render(request, 'purchases/detail.html', {
        'purchase': purchase,
        'items': purchase.items.all(),
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
