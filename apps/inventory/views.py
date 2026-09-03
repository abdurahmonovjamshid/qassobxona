from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.inventory.models import StockMovement
from apps.inventory.services import inventory_service
from apps.products.models import Product


@login_required
def inventory_list(request):
    stock_rows = []
    for product in Product.objects.filter(active=True):
        qty = inventory_service.get_stock(product)
        stock_rows.append({
            'product': product,
            'quantity': qty,
            'avg_cost': inventory_service.get_weighted_average_cost(product),
        })
    stock_rows.sort(key=lambda r: r['product'].name)

    movements = StockMovement.objects.select_related('product').all()
    product_id = request.GET.get('product')
    movement_type = request.GET.get('movement_type')
    if product_id:
        movements = movements.filter(product_id=product_id)
    if movement_type:
        movements = movements.filter(movement_type=movement_type)

    return render(request, 'inventory/list.html', {
        'stock_rows': stock_rows,
        'movements': movements[:200],
        'products': Product.objects.filter(active=True),
        'movement_types': StockMovement.MovementType.choices,
    })
