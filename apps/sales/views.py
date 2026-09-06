import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.common.date_filters import get_date_range
from apps.customers.models import Customer
from apps.inventory.services import inventory_service
from apps.payments.services import payment_service
from apps.products.models import Product
from apps.sales.forms import SaleForm, SaleItemFormSet
from apps.sales.models import Sale
from apps.sales.services import sale_service


def _products_json():
    products = Product.objects.filter(active=True).select_related('category').order_by('name')
    stock_map = inventory_service.get_all_stock()
    pieces_map = inventory_service.get_all_stock_pieces()
    return json.dumps([
        {
            'id': p.id,
            'name': p.name,
            'price': str(p.sale_price),
            'unit': p.unit,
            'image': p.image.url if p.image else None,
            'stock': str(stock_map.get(p.id, 0)),
            'stock_pieces': pieces_map.get(p.id, 0),
            'category': p.category.code,
            'category_label': p.category.name,
        }
        for p in products
    ])


def _customers_json():
    customers = Customer.objects.filter(active=True).order_by('name')
    return json.dumps([
        {'id': c.id, 'name': c.name, 'phone': c.phone}
        for c in customers
    ])


def _cart_json_from_formset(formset):
    """Validatsiya xatosidan keyin formani qayta ko'rsatishda savatchani
    (katalog UI holatini) tiklash uchun — bog'langan formset qatorlaridan
    mahsulot/miqdor/narx/chegirmani o'qib, JS kutgan shaklga o'giradi."""
    rows = []
    for f in formset.forms:
        product_id = f['product'].value()
        quantity = f['quantity'].value()
        if not product_id or not quantity:
            continue
        rows.append({
            'product_id': product_id,
            'quantity': quantity,
            'pieces': f['pieces'].value() or '0',
            'price': f['price'].value() or '0',
            'discount': f['discount'].value() or '0',
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
            'quantity': r['quantity'],
            'pieces': r['pieces'],
            'price': r['price'],
            'discount': r['discount'],
        })
    return json.dumps(cart)


def _generate_sale_number():
    today = timezone.localdate()
    prefix = f"S{today.strftime('%Y%m%d')}"
    last = Sale.objects.filter(sale_number__startswith=prefix).order_by('-sale_number').first()
    seq = int(last.sale_number.rsplit('-', 1)[-1]) + 1 if last else 1
    return f"{prefix}-{seq:04d}"


@login_required
def sale_list(request):
    sales = Sale.objects.select_related('customer').all()

    customer_id = request.GET.get('customer')
    status = request.GET.get('status')
    date_from, date_to = get_date_range(request)

    if customer_id:
        sales = sales.filter(customer_id=customer_id)
    if status:
        sales = sales.filter(status=status)
    if date_from:
        sales = sales.filter(date__gte=date_from)
    if date_to:
        sales = sales.filter(date__lte=date_to)

    return render(request, 'sales/list.html', {
        'sales': sales[:200],
        'statuses': Sale.Status.choices,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
def sale_create(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            formset = SaleItemFormSet(request.POST, instance=sale)
            if formset.is_valid():
                try:
                    with transaction.atomic():
                        sale.sale_number = _generate_sale_number()
                        sale.status = Sale.Status.DRAFT
                        sale.save()
                        formset.instance = sale
                        formset.save()

                        sale_service.confirm_sale(sale, user=request.user)

                        paid_amount = form.cleaned_data.get('paid_amount') or Decimal('0')
                        if paid_amount > 0:
                            payment_service.create_payment(
                                amount=paid_amount,
                                payment_type=form.cleaned_data.get('payment_type') or 'CASH',
                                date=sale.date, customer=sale.customer, sale=sale, user=request.user,
                            )
                    messages.success(request, f"Sotuv {sale.sale_number} muvaffaqiyatli tasdiqlandi.")
                    return redirect('sales:detail', pk=sale.pk)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
        else:
            formset = SaleItemFormSet(request.POST)
    else:
        form = SaleForm(initial={'date': timezone.localdate()})
        formset = SaleItemFormSet()

    return render(request, 'sales/form.html', {
        'form': form,
        'formset': formset,
        'products_json': _products_json(),
        'customers_json': _customers_json(),
        'initial_cart_json': _cart_json_from_formset(formset) if request.method == 'POST' else '[]',
    })


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('customer'), pk=pk)
    return render(request, 'sales/detail.html', {
        'sale': sale,
        'items': sale.items.select_related('product').all(),
        'payments': sale.payments.all(),
    })


@login_required
def sale_cancel(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == 'POST':
        try:
            sale_service.cancel_sale(sale, user=request.user)
            messages.success(request, f"Sotuv {sale.sale_number} bekor qilindi.")
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return redirect('sales:detail', pk=pk)
