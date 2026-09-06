import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.inventory.services import inventory_service
from apps.kassa.services import cash_service
from apps.payments.models import Payment
from apps.products.models import Product
from apps.purchases.models import Purchase
from apps.sales.models import Sale, SaleItem
from apps.suppliers.models import Supplier


@login_required
def index(request):
    today = timezone.localdate()

    todays_sales = Sale.objects.filter(date=today, status=Sale.Status.CONFIRMED)
    todays_sale_items = SaleItem.objects.filter(sale__in=todays_sales)

    today_sales_count = todays_sales.count()
    today_sales_total = todays_sales.aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    today_gross_profit = todays_sale_items.aggregate(s=Sum('profit'))['s'] or Decimal('0')
    today_expenses = Expense.objects.filter(date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    today_net_profit = today_gross_profit - today_expenses

    # Qarz = boshlang'ich saldo + jami sotuv/xarid - jami to'lov (sotuv/xaridga
    # bog'liq bo'lmagan umumiy to'lovlar ham hisobga olinadi). Har bir mijoz/
    # supplierning `get_total_debt()` yig'indisiga teng, lekin bitta agregatsiya
    # so'rovi bilan hisoblanadi.
    customers_opening = Customer.objects.aggregate(s=Sum('opening_balance'))['s'] or Decimal('0')
    total_sales_all = Sale.objects.filter(status=Sale.Status.CONFIRMED).aggregate(
        s=Sum('total_amount'))['s'] or Decimal('0')
    total_customer_payments_all = Payment.objects.filter(customer__isnull=False).aggregate(
        s=Sum('amount'))['s'] or Decimal('0')
    debitor_total = customers_opening + total_sales_all - total_customer_payments_all

    suppliers_opening = Supplier.objects.aggregate(s=Sum('opening_balance'))['s'] or Decimal('0')
    total_purchases_all = Purchase.objects.filter(status=Purchase.Status.CONFIRMED).aggregate(
        s=Sum('total_amount'))['s'] or Decimal('0')
    total_supplier_payments_all = Payment.objects.filter(supplier__isnull=False).aggregate(
        s=Sum('amount'))['s'] or Decimal('0')
    creditor_total = suppliers_opening + total_purchases_all - total_supplier_payments_all

    customer_payments_today = Payment.objects.filter(
        date=today, customer__isnull=False).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    supplier_payments_today = Payment.objects.filter(
        date=today, supplier__isnull=False).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    naqd_qoldiq = customer_payments_today - supplier_payments_today - today_expenses

    stock_rows = []
    total_stock = Decimal('0')
    for product in Product.objects.filter(active=True):
        qty = inventory_service.get_stock(product)
        total_stock += qty
        if qty > 0:
            stock_rows.append({'product': product, 'quantity': qty})
    stock_rows.sort(key=lambda r: r['quantity'], reverse=True)

    daily_labels, daily_values = [], []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        total = Sale.objects.filter(date=day, status=Sale.Status.CONFIRMED).aggregate(
            s=Sum('total_amount'))['s'] or Decimal('0')
        daily_labels.append(day.strftime('%d.%m'))
        daily_values.append(float(total))

    top_products_qs = (
        SaleItem.objects.filter(sale__status=Sale.Status.CONFIRMED, sale__date__month=today.month,
                                 sale__date__year=today.year)
        .values('product__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:5]
    )
    top_products_labels = [row['product__name'] for row in top_products_qs]
    top_products_values = [float(row['total_qty']) for row in top_products_qs]

    top_customers_qs = (
        Sale.objects.filter(status=Sale.Status.CONFIRMED, date__month=today.month, date__year=today.year)
        .values('customer__name')
        .annotate(total=Sum('total_amount'))
        .order_by('-total')[:10]
    )
    top_customers_labels = [row['customer__name'] for row in top_customers_qs]
    top_customers_values = [float(row['total']) for row in top_customers_qs]

    top_suppliers_qs = (
        Purchase.objects.filter(status=Purchase.Status.CONFIRMED, date__month=today.month, date__year=today.year)
        .values('supplier__name')
        .annotate(total=Sum('total_amount'))
        .order_by('-total')[:10]
    )
    top_suppliers_labels = [row['supplier__name'] for row in top_suppliers_qs]
    top_suppliers_values = [float(row['total']) for row in top_suppliers_qs]

    kassa_balance = cash_service.get_balance()

    context = {
        'today': today,
        'today_sales_count': today_sales_count,
        'today_sales_total': today_sales_total,
        'today_gross_profit': today_gross_profit,
        'today_expenses': today_expenses,
        'today_net_profit': today_net_profit,
        'debitor_total': debitor_total,
        'creditor_total': creditor_total,
        'naqd_qoldiq': naqd_qoldiq,
        'customer_payments_today': customer_payments_today,
        'supplier_payments_today': supplier_payments_today,
        'total_stock': total_stock,
        'stock_rows': stock_rows[:10],
        'daily_labels': json.dumps(daily_labels),
        'daily_values': json.dumps(daily_values),
        'top_products_labels': json.dumps(top_products_labels),
        'top_products_values': json.dumps(top_products_values),
        'debitor_creditor_values': json.dumps([float(debitor_total), float(creditor_total)]),
        'kassa_balance': kassa_balance,
        'top_customers_labels': json.dumps(top_customers_labels),
        'top_customers_values': json.dumps(top_customers_values),
        'top_suppliers_labels': json.dumps(top_suppliers_labels),
        'top_suppliers_values': json.dumps(top_suppliers_values),
    }
    return render(request, 'dashboard/index.html', context)
