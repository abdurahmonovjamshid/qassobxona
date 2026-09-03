import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.butchering.forms import ButcheringForm, ButcheringOutputFormSet
from apps.butchering.models import Butchering
from apps.butchering.services import butchering_service
from apps.products.models import Product
from apps.purchases.models import Purchase


def _products_json():
    products = Product.objects.filter(active=True).order_by('name')
    return json.dumps([
        {'id': p.id, 'name': p.name, 'image': p.image.url if p.image else None}
        for p in products
    ])


def _purchases_json():
    purchases = Purchase.objects.filter(status=Purchase.Status.CONFIRMED).select_related('product')
    return json.dumps([
        {
            'id': p.id,
            'product_id': p.product_id,
            'net_weight': str(p.net_weight),
        }
        for p in purchases
    ])


@login_required
def butchering_list(request):
    items = Butchering.objects.select_related('purchase', 'input_product').all()
    status = request.GET.get('status')
    if status:
        items = items.filter(status=status)
    return render(request, 'butchering/list.html', {
        'items': items[:200],
        'statuses': Butchering.Status.choices,
    })


@login_required
def butchering_create(request):
    if request.method == 'POST':
        form = ButcheringForm(request.POST)
        if form.is_valid():
            butchering = form.save(commit=False)
            formset = ButcheringOutputFormSet(request.POST, instance=butchering)
            if formset.is_valid():
                try:
                    with transaction.atomic():
                        butchering.status = Butchering.Status.DRAFT
                        butchering.save()
                        formset.instance = butchering
                        formset.save()

                        butchering_service.confirm_butchering(butchering, user=request.user)
                    messages.success(request, "Bo'laklash muvaffaqiyatli tasdiqlandi.")
                    return redirect('butchering:detail', pk=butchering.pk)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
        else:
            formset = ButcheringOutputFormSet(request.POST)
    else:
        initial = {'date': timezone.localdate()}
        purchase_id = request.GET.get('purchase')
        if purchase_id:
            initial['purchase'] = purchase_id
            purchase = Purchase.objects.filter(pk=purchase_id).first()
            if purchase and purchase.product_id:
                initial['input_product'] = purchase.product_id
                initial['input_weight'] = purchase.net_weight
        form = ButcheringForm(initial=initial)
        formset = ButcheringOutputFormSet()

    return render(request, 'butchering/form.html', {
        'form': form, 'formset': formset,
        'products_json': _products_json(),
        'purchases_json': _purchases_json(),
    })


@login_required
def butchering_detail(request, pk):
    butchering = get_object_or_404(
        Butchering.objects.select_related('purchase', 'input_product'), pk=pk)
    return render(request, 'butchering/detail.html', {
        'butchering': butchering,
        'outputs': butchering.outputs.select_related('product').all(),
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
