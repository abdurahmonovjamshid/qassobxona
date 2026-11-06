import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.inventory.forms import (
    InventoryCountForm, InventoryCountItemFormSet, InventoryImportForm,
    StockTransferForm, StockTransferItemFormSet,
)
from apps.inventory.models import InventoryCount, InventoryCountItem, StockMovement, StockTransfer, Warehouse
from apps.inventory.services import excel_service, inventory_service
from apps.products.models import Product


@login_required
def inventory_list(request):
    warehouses = list(Warehouse.objects.filter(active=True))
    kg_maps = [inventory_service.get_all_stock(w) for w in warehouses]
    stock_rows = []
    for product in Product.objects.filter(active=True).select_related('category'):
        qty = inventory_service.get_stock(product)
        stock_rows.append({
            'product': product,
            'quantity': qty,
            'by_warehouse': [m.get(product.id, 0) for m in kg_maps],
            'pieces': inventory_service.get_stock_pieces(product),
            'avg_cost': inventory_service.get_weighted_average_cost(product),
        })
    stock_rows.sort(key=lambda r: r['product'].name)

    movements = StockMovement.objects.select_related('product', 'warehouse').all()
    product_id = request.GET.get('product')
    movement_type = request.GET.get('movement_type')
    warehouse_id = request.GET.get('warehouse')
    if product_id:
        movements = movements.filter(product_id=product_id)
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    if warehouse_id:
        movements = movements.filter(warehouse_id=warehouse_id)

    return render(request, 'inventory/list.html', {
        'stock_rows': stock_rows,
        'movements': movements[:200],
        'products': Product.objects.filter(active=True),
        'movement_types': StockMovement.MovementType.choices,
        'warehouses': warehouses,
    })


@login_required
def inventory_count_list(request):
    counts = InventoryCount.objects.all()
    return render(request, 'inventory/count_list.html', {'counts': counts[:200]})


@login_required
def inventory_count_create(request):
    if request.method == 'POST':
        form = InventoryCountForm(request.POST)
        if form.is_valid():
            count = form.save(commit=False)
            formset = InventoryCountItemFormSet(request.POST, instance=count)
            if formset.is_valid():
                try:
                    with transaction.atomic():
                        count.status = InventoryCount.Status.DRAFT
                        count.created_by = request.user
                        count.save()
                        formset.instance = count
                        formset.save()
                        inventory_service.confirm_inventory_count(count, user=request.user)
                    messages.success(request, "Inventarizatsiya muvaffaqiyatli tasdiqlandi.")
                    return redirect('inventory:count_detail', pk=count.pk)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
        else:
            formset = InventoryCountItemFormSet(request.POST)
    else:
        form = InventoryCountForm(initial={'date': timezone.localdate()})
        formset = InventoryCountItemFormSet()

    stock_fields = inventory_service.stock_fields_by_warehouse()
    products_json = json.dumps([
        {'id': p.id, 'name': p.name, **stock_fields(p.id)}
        for p in Product.objects.filter(active=True).order_by('name')
    ])
    return render(request, 'inventory/count_form.html', {
        'form': form, 'formset': formset, 'products_json': products_json,
    })


@login_required
def inventory_count_detail(request, pk):
    count = get_object_or_404(InventoryCount, pk=pk)
    return render(request, 'inventory/count_detail.html', {
        'count': count,
        'items': count.items.select_related('product').all(),
    })


@login_required
def inventory_export(request):
    warehouse = Warehouse.objects.filter(pk=request.GET.get('warehouse') or None).first()
    return excel_service.export_inventory_workbook(warehouse)


@login_required
def inventory_import(request):
    if request.method == 'POST':
        form = InventoryImportForm(request.POST, request.FILES)
        if form.is_valid():
            rows, errors = excel_service.parse_inventory_workbook(form.cleaned_data['file'])
            if errors:
                for err in errors:
                    messages.error(request, err)
            else:
                try:
                    with transaction.atomic():
                        count = InventoryCount.objects.create(
                            date=timezone.localdate(),
                            warehouse=form.cleaned_data['warehouse'],
                            notes="Excel orqali import qilingan.",
                            status=InventoryCount.Status.DRAFT,
                            created_by=request.user,
                        )
                        for row in rows:
                            InventoryCountItem.objects.create(
                                count=count, product=row['product'],
                                counted_kg=row['kg'], counted_pieces=row['pieces'],
                                unit_cost=row['unit_cost'],
                            )
                        inventory_service.confirm_inventory_count(count, user=request.user)
                    messages.success(
                        request, f"{len(rows)} ta mahsulot Excel orqali yangilandi."
                    )
                    return redirect('inventory:count_detail', pk=count.pk)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
    else:
        form = InventoryImportForm(initial={'warehouse': inventory_service.resolve_warehouse(None)})
    return render(request, 'inventory/import.html', {
        'form': form, 'warehouses': Warehouse.objects.filter(active=True),
        'warehouse': inventory_service.resolve_warehouse(None),
    })


@login_required
def transfer_list(request):
    transfers = StockTransfer.objects.select_related('from_warehouse', 'to_warehouse').prefetch_related('items')
    return render(request, 'inventory/transfer_list.html', {'transfers': transfers[:200]})


@login_required
def transfer_create(request):
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        formset = StockTransferItemFormSet(request.POST)
        if form.is_valid():
            transfer = form.save(commit=False)
            formset = StockTransferItemFormSet(request.POST, instance=transfer)
            if formset.is_valid():
                try:
                    with transaction.atomic():
                        transfer.status = StockTransfer.Status.DRAFT
                        transfer.created_by = request.user
                        transfer.save()
                        formset.instance = transfer
                        formset.save()
                        inventory_service.confirm_transfer(transfer, user=request.user)
                    messages.success(request, "Ko'chirish muvaffaqiyatli tasdiqlandi.")
                    return redirect('inventory:transfer_detail', pk=transfer.pk)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
    else:
        form = StockTransferForm(initial={'date': timezone.localdate()})
        formset = StockTransferItemFormSet()

    stock_fields = inventory_service.stock_fields_by_warehouse()
    products_json = json.dumps([
        {'id': p.id, 'name': p.name, **stock_fields(p.id)}
        for p in Product.objects.filter(active=True).order_by('name')
    ])
    return render(request, 'inventory/transfer_form.html', {
        'form': form, 'formset': formset, 'products_json': products_json,
    })


@login_required
def transfer_detail(request, pk):
    transfer = get_object_or_404(StockTransfer.objects.select_related('from_warehouse', 'to_warehouse'), pk=pk)
    return render(request, 'inventory/transfer_detail.html', {
        'transfer': transfer,
        'items': transfer.items.select_related('product').all(),
    })


@login_required
def transfer_cancel(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    if request.method == 'POST':
        try:
            inventory_service.cancel_transfer(transfer, user=request.user)
            messages.success(request, "Ko'chirish bekor qilindi.")
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return redirect('inventory:transfer_detail', pk=transfer.pk)
