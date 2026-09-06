"""Hisobotlar uchun agregatsiya funksiyalari. Har biri filtrlarni qabul qiladi
va shablonda ko'rsatish uchun tayyor dict/queryset qaytaradi."""
from decimal import Decimal

from django.db.models import Sum

from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.inventory.models import StockMovement
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem
from apps.sales.models import Sale, SaleItem
from apps.suppliers.models import Supplier

ZERO = Decimal('0')


def sales_report(*, date_from=None, date_to=None, customer_id=None, product_id=None):
    sales = Sale.objects.filter(status=Sale.Status.CONFIRMED).select_related('customer')
    if date_from:
        sales = sales.filter(date__gte=date_from)
    if date_to:
        sales = sales.filter(date__lte=date_to)
    if customer_id:
        sales = sales.filter(customer_id=customer_id)

    items = SaleItem.objects.filter(sale__in=sales).select_related('sale', 'product')
    if product_id:
        items = items.filter(product_id=product_id)
        sales = sales.filter(items__product_id=product_id).distinct()

    return {
        'sales': sales.order_by('-date'),
        'items': items,
        'total_amount': sales.aggregate(s=Sum('total_amount'))['s'] or ZERO,
        'total_paid': sales.aggregate(s=Sum('paid_amount'))['s'] or ZERO,
        'total_debt': sales.aggregate(s=Sum('debt_amount'))['s'] or ZERO,
    }


def purchase_report(*, date_from=None, date_to=None, supplier_id=None):
    purchases = Purchase.objects.filter(status=Purchase.Status.CONFIRMED).select_related('supplier').prefetch_related('items')
    if date_from:
        purchases = purchases.filter(date__gte=date_from)
    if date_to:
        purchases = purchases.filter(date__lte=date_to)
    if supplier_id:
        purchases = purchases.filter(supplier_id=supplier_id)

    total_weight = PurchaseItem.objects.filter(purchase__in=purchases).aggregate(s=Sum('net_weight'))['s'] or ZERO

    return {
        'purchases': purchases.order_by('-date'),
        'total_amount': purchases.aggregate(s=Sum('total_amount'))['s'] or ZERO,
        'total_paid': purchases.aggregate(s=Sum('paid_amount'))['s'] or ZERO,
        'total_debt': purchases.aggregate(s=Sum('debt_amount'))['s'] or ZERO,
        'total_weight': total_weight,
    }


def inventory_report():
    from apps.inventory.services import inventory_service

    rows = []
    for product in Product.objects.filter(active=True):
        total_in = StockMovement.objects.filter(
            product=product, direction=StockMovement.Direction.IN).aggregate(s=Sum('quantity'))['s'] or ZERO
        total_out = StockMovement.objects.filter(
            product=product, direction=StockMovement.Direction.OUT).aggregate(s=Sum('quantity'))['s'] or ZERO
        rows.append({
            'product': product,
            'total_in': total_in,
            'total_out': total_out,
            'stock': total_in - total_out,
            'avg_cost': inventory_service.get_weighted_average_cost(product),
        })
    return rows


def debtor_report():
    rows = []
    for customer in Customer.objects.all():
        debt = customer.get_total_debt()
        if debt > 0:
            rows.append({'customer': customer, 'debt': debt})
    rows.sort(key=lambda r: r['debt'], reverse=True)
    return rows


def creditor_report():
    rows = []
    for supplier in Supplier.objects.all():
        debt = supplier.get_total_debt()
        if debt > 0:
            rows.append({'supplier': supplier, 'debt': debt})
    rows.sort(key=lambda r: r['debt'], reverse=True)
    return rows


def profit_report(*, date_from=None, date_to=None):
    items = SaleItem.objects.filter(sale__status=Sale.Status.CONFIRMED)
    expenses = Expense.objects.all()
    if date_from:
        items = items.filter(sale__date__gte=date_from)
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        items = items.filter(sale__date__lte=date_to)
        expenses = expenses.filter(date__lte=date_to)

    revenue = items.aggregate(s=Sum('total'))['s'] or ZERO
    gross_profit = items.aggregate(s=Sum('profit'))['s'] or ZERO
    cost = revenue - gross_profit
    expenses_total = expenses.aggregate(s=Sum('amount'))['s'] or ZERO
    net_profit = gross_profit - expenses_total

    return {
        'revenue': revenue,
        'cost': cost,
        'gross_profit': gross_profit,
        'expenses_total': expenses_total,
        'net_profit': net_profit,
    }
