import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.butchering.forms import (
    ButcheringExpenseFormSet, ButcheringForm, ButcheringOutputFormSet,
    ButcheringSpecificationForm, ButcheringSpecificationItemFormSet,
)
from apps.butchering.models import Butchering, ButcheringSpecification
from apps.butchering.services import butchering_service
from apps.common.date_filters import get_date_range
from apps.inventory.services import inventory_service
from apps.products.models import Product
from apps.purchases.models import Purchase


def _products_json():
    products = Product.objects.filter(active=True).select_related('category').order_by('name')
    stock_map = inventory_service.get_all_stock()
    pieces_map = inventory_service.get_all_stock_pieces()
    return json.dumps([
        {
            'id': p.id, 'name': p.name, 'image': p.image.url if p.image else None,
            'category': p.category.code, 'category_label': p.category.name,
            'stock': str(stock_map.get(p.id, 0)), 'stock_pieces': pieces_map.get(p.id, 0),
        }
        for p in products
    ])


def _outputs_json_from_formset(formset):
    """Validatsiya xatosidan keyin formani qayta ko'rsatishda output
    kartochkalarini tiklash uchun — bog'langan formset qatorlaridan
    mahsulot/miqdor/son o'qib, JS kutgan shaklga o'giradi."""
    rows = []
    for f in formset.forms:
        product_id = f['product'].value()
        if not product_id:
            continue
        rows.append({
            'product_id': product_id,
            'quantity': f['quantity'].value() or '0',
            'pieces': f['pieces'].value() or '0',
        })
    if not rows:
        return '[]'

    products = Product.objects.in_bulk([r['product_id'] for r in rows])
    outputs = []
    for r in rows:
        product = products.get(int(r['product_id']))
        if not product:
            continue
        outputs.append({
            'id': product.id,
            'name': product.name,
            'image': product.image.url if product.image else None,
            'quantity': r['quantity'],
            'pieces': r['pieces'],
        })
    return json.dumps(outputs)


def _specifications_json():
    specs = ButcheringSpecification.objects.filter(active=True).prefetch_related('items')
    return json.dumps([
        {
            'id': s.id,
            'name': s.name,
            'parent_product_id': s.parent_product_id,
            'items': [{'child_product_id': item.child_product_id} for item in s.items.all()],
        }
        for s in specs
    ])


@login_required
def butchering_list(request):
    items = Butchering.objects.select_related('purchase', 'input_product').all()
    status = request.GET.get('status')
    date_from, date_to = get_date_range(request)
    if status:
        items = items.filter(status=status)
    if date_from:
        items = items.filter(date__gte=date_from)
    if date_to:
        items = items.filter(date__lte=date_to)
    return render(request, 'butchering/list.html', {
        'items': items[:200],
        'statuses': Butchering.Status.choices,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
def butchering_create(request):
    if request.method == 'POST':
        form = ButcheringForm(request.POST)
        if form.is_valid():
            butchering = form.save(commit=False)
            formset = ButcheringOutputFormSet(request.POST, instance=butchering, prefix='outputs')
            expense_formset = ButcheringExpenseFormSet(request.POST, instance=butchering, prefix='expenses')
            if formset.is_valid() and expense_formset.is_valid():
                try:
                    with transaction.atomic():
                        butchering.status = Butchering.Status.DRAFT
                        butchering.save()
                        formset.instance = butchering
                        formset.save()
                        expense_formset.instance = butchering
                        expense_formset.save()

                        butchering_service.confirm_butchering(butchering, user=request.user)
                    messages.success(request, "Bo'laklash muvaffaqiyatli tasdiqlandi.")
                    return redirect('butchering:detail', pk=butchering.pk)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
        else:
            formset = ButcheringOutputFormSet(request.POST, prefix='outputs')
            expense_formset = ButcheringExpenseFormSet(request.POST, prefix='expenses')
        outputs_json = _outputs_json_from_formset(formset)
    else:
        initial = {'date': timezone.localdate()}
        purchase_id = request.GET.get('purchase')
        if purchase_id:
            purchase = Purchase.objects.filter(pk=purchase_id).prefetch_related('items').first()
            if purchase:
                items = list(purchase.items.all())
                if len(items) == 1:
                    initial['input_product'] = items[0].product_id
                    initial['input_weight'] = items[0].net_weight
                    initial['input_pieces'] = items[0].pieces
        form = ButcheringForm(initial=initial)
        formset = ButcheringOutputFormSet(prefix='outputs')
        expense_formset = ButcheringExpenseFormSet(prefix='expenses')
        outputs_json = '[]'

    return render(request, 'butchering/form.html', {
        'form': form, 'formset': formset, 'expense_formset': expense_formset,
        'products_json': _products_json(),
        'specifications_json': _specifications_json(),
        'outputs_json': outputs_json,
    })


@login_required
def butchering_detail(request, pk):
    butchering = get_object_or_404(
        Butchering.objects.select_related('purchase', 'input_product'), pk=pk)
    return render(request, 'butchering/detail.html', {
        'butchering': butchering,
        'outputs': butchering.outputs.select_related('product').all(),
        'expenses': butchering.extra_expenses.all(),
    })


@login_required
def butchering_cancel(request, pk):
    butchering = get_object_or_404(Butchering, pk=pk)
    if request.method == 'POST':
        try:
            butchering_service.cancel_butchering(butchering, user=request.user)
            messages.success(request, "Bo'laklash bekor qilindi.")
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return redirect('butchering:detail', pk=pk)


@login_required
def specification_list(request):
    specs = ButcheringSpecification.objects.select_related('parent_product').prefetch_related('items__child_product')
    product_id = request.GET.get('product')
    if product_id:
        specs = specs.filter(parent_product_id=product_id)
    return render(request, 'butchering/specification_list.html', {
        'specs': specs,
        'products': Product.objects.filter(active=True),
    })


@login_required
def specification_create(request):
    if request.method == 'POST':
        form = ButcheringSpecificationForm(request.POST)
        if form.is_valid():
            spec = form.save(commit=False)
            formset = ButcheringSpecificationItemFormSet(request.POST, instance=spec)
            if formset.is_valid():
                with transaction.atomic():
                    spec.save()
                    formset.instance = spec
                    formset.save()
                messages.success(request, f"'{spec.name}' spetsifikatsiyasi qo'shildi.")
                return redirect('butchering:specification_list')
        else:
            formset = ButcheringSpecificationItemFormSet(request.POST)
    else:
        initial = {}
        product_id = request.GET.get('product')
        if product_id:
            initial['parent_product'] = product_id
        form = ButcheringSpecificationForm(initial=initial)
        formset = ButcheringSpecificationItemFormSet()

    return render(request, 'butchering/specification_form.html', {'form': form, 'formset': formset, 'title': 'Yangi spetsifikatsiya'})


@login_required
def specification_update(request, pk):
    spec = get_object_or_404(ButcheringSpecification, pk=pk)
    if request.method == 'POST':
        form = ButcheringSpecificationForm(request.POST, instance=spec)
        if form.is_valid():
            formset = ButcheringSpecificationItemFormSet(request.POST, instance=spec)
            if formset.is_valid():
                with transaction.atomic():
                    form.save()
                    formset.save()
                messages.success(request, f"'{spec.name}' spetsifikatsiyasi yangilandi.")
                return redirect('butchering:specification_list')
        else:
            formset = ButcheringSpecificationItemFormSet(request.POST, instance=spec)
    else:
        form = ButcheringSpecificationForm(instance=spec)
        formset = ButcheringSpecificationItemFormSet(instance=spec)

    return render(request, 'butchering/specification_form.html', {
        'form': form, 'formset': formset, 'title': spec.name, 'spec': spec,
    })
