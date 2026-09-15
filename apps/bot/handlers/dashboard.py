"""Dashboard — `apps/dashboard/views.py::index` bilan bir xil agregatsiya
so'rovlari, matn ko'rinishida (TZ.txt 25-bo'limdagi mock bilan mos)."""
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import kg, som
from apps.bot.handlers.common import register_menu
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.inventory.services import inventory_service
from apps.kassa.services import cash_service
from apps.payments.models import Payment
from apps.products.models import Product
from apps.purchases.models import Purchase
from apps.sales.models import Sale, SaleItem
from apps.suppliers.models import Supplier


@register_menu(keyboards.MENU_DASHBOARD)
def dashboard(message, tg_user):
    today = timezone.localdate()

    todays_sales = Sale.objects.filter(date=today, status=Sale.Status.CONFIRMED)
    todays_sale_items = SaleItem.objects.filter(sale__in=todays_sales)
    today_sales_count = todays_sales.count()
    today_sales_total = todays_sales.aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    today_gross_profit = todays_sale_items.aggregate(s=Sum('profit'))['s'] or Decimal('0')
    today_expenses = Expense.objects.filter(date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    today_net_profit = today_gross_profit - today_expenses

    customers_opening = Customer.objects.aggregate(s=Sum('opening_balance'))['s'] or Decimal('0')
    total_sales_all = Sale.objects.filter(status=Sale.Status.CONFIRMED).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    total_customer_payments_all = Payment.objects.filter(customer__isnull=False).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    debitor_total = customers_opening + total_sales_all - total_customer_payments_all

    suppliers_opening = Supplier.objects.aggregate(s=Sum('opening_balance'))['s'] or Decimal('0')
    total_purchases_all = Purchase.objects.filter(status=Purchase.Status.CONFIRMED).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    total_supplier_payments_all = Payment.objects.filter(supplier__isnull=False).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    creditor_total = suppliers_opening + total_purchases_all - total_supplier_payments_all

    total_stock = Decimal('0')
    stock_rows = []
    for product in Product.objects.filter(active=True):
        qty = inventory_service.get_stock(product)
        total_stock += qty
        if qty > 0:
            stock_rows.append((product.name, qty))
    stock_rows.sort(key=lambda r: r[1], reverse=True)

    kassa_balance = cash_service.get_balance()

    lines = [
        '========================================',
        '          QASSOBXONA DASHBOARD',
        '========================================',
        '',
        'Bugungi savdo',
        f'{som(today_sales_total)} ({today_sales_count} ta sotuv)',
        '',
        'Bugungi yalpi foyda',
        som(today_gross_profit),
        '',
        'Bugungi sof foyda',
        som(today_net_profit),
        '',
        'Debitor',
        som(debitor_total),
        '',
        'Kreditor',
        som(creditor_total),
        '',
        'Kassa balansi',
        som(kassa_balance),
        '',
        'Ombor (jami)',
        kg(total_stock),
        '========================================',
        '',
        "OMBOR QOLDIG'I (top 10)",
        '',
    ]
    for name, qty in stock_rows[:10]:
        lines.append(f'{name}: {kg(qty)}')

    bot.send_message(message.chat.id, '\n'.join(lines))
