from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.common.date_filters import get_date_range
from apps.customers.models import Customer
from apps.products.models import Product
from apps.reports.services import report_service
from apps.suppliers.models import Supplier


@login_required
def reports_index(request):
    return render(request, 'reports/index.html')


@login_required
def sales_report_view(request):
    data = report_service.sales_report(
        date_from=request.GET.get('date_from') or None,
        date_to=request.GET.get('date_to') or None,
        customer_id=request.GET.get('customer') or None,
        product_id=request.GET.get('product') or None,
    )
    data.update({'customers': Customer.objects.all(), 'products': Product.objects.filter(active=True)})
    return render(request, 'reports/sales.html', data)


@login_required
def purchase_report_view(request):
    data = report_service.purchase_report(
        date_from=request.GET.get('date_from') or None,
        date_to=request.GET.get('date_to') or None,
        supplier_id=request.GET.get('supplier') or None,
    )
    data.update({'suppliers': Supplier.objects.all()})
    return render(request, 'reports/purchases.html', data)


@login_required
def inventory_report_view(request):
    return render(request, 'reports/inventory.html', {'rows': report_service.inventory_report()})


@login_required
def debtor_report_view(request):
    return render(request, 'reports/debtor.html', {'rows': report_service.debtor_report()})


@login_required
def creditor_report_view(request):
    return render(request, 'reports/creditor.html', {'rows': report_service.creditor_report()})


@login_required
def profit_report_view(request):
    date_from, date_to = get_date_range(request)
    data = report_service.profit_report(date_from=date_from or None, date_to=date_to or None)
    data.update({'date_from': date_from, 'date_to': date_to})
    return render(request, 'reports/profit.html', data)
