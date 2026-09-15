"""Pick-list qatorlari. Har biri veb-saytdagi tegishli Django Form'ning
querysetini AYNAN takrorlaydi — filtrlash mantig'ini qayta yozmaslik uchun."""
from apps.inventory.services import inventory_service


def active_products():
    from apps.products.models import Product
    return [(p.id, p.name) for p in Product.objects.filter(active=True).order_by('name')]


def active_products_with_stock():
    from apps.products.models import Product
    stock = inventory_service.get_all_stock()
    return [
        (p.id, f'{p.name} ({stock.get(p.id, 0)} kg)')
        for p in Product.objects.filter(active=True).order_by('name')
    ]


def butchering_input_products():
    # apps/butchering/forms.py::ButcheringForm bilan bir xil queryset —
    # faqat kamida bitta faol spetsifikatsiyasi bor mahsulotlar.
    from apps.products.models import Product
    return [
        (p.id, p.name)
        for p in Product.objects.filter(active=True, specifications__active=True).distinct().order_by('name')
    ]


def active_specifications(parent_product_id):
    from apps.butchering.models import ButcheringSpecification
    return [
        (s.id, s.name)
        for s in ButcheringSpecification.objects.filter(active=True, parent_product_id=parent_product_id)
    ]


def active_customers():
    from apps.customers.models import Customer
    return [(c.id, c.name) for c in Customer.objects.filter(active=True).order_by('name')]


def active_suppliers():
    from apps.suppliers.models import Supplier
    return [(s.id, s.name) for s in Supplier.objects.filter(active=True).order_by('name')]


def active_expense_categories():
    from apps.expenses.models import ExpenseCategory
    return [(c.id, c.name) for c in ExpenseCategory.objects.filter(active=True).order_by('name')]


PURCHASE_EXPENSE_TYPES = [
    ('TRANSPORT', 'Transport'),
    ('LOADING', 'Yuklash'),
    ('UNLOADING', 'Tushirish'),
    ('SLAUGHTER', "So'yish"),
    ('OTHER', 'Boshqa'),
]

BUTCHERING_EXPENSE_TYPES = [
    ('LABOR', 'Ishchi kuchi'),
    ('PACKAGING', 'Qadoqlash'),
    ('OTHER', 'Boshqa'),
]

PAYMENT_TYPES = [
    ('CASH', 'Naqd'),
    ('CARD', 'Karta'),
    ('TRANSFER', "O'tkazma"),
    ('OTHER', 'Boshqa'),
]


def confirmed_sales_with_debt(customer_id=None):
    from apps.sales.models import Sale
    qs = Sale.objects.filter(status=Sale.Status.CONFIRMED, debt_amount__gt=0)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    return [(s.id, f'{s.sale_number} (qarz: {s.debt_amount})') for s in qs.order_by('-date')[:30]]


def confirmed_purchases_with_debt(supplier_id=None):
    from apps.purchases.models import Purchase
    qs = Purchase.objects.filter(status=Purchase.Status.CONFIRMED, debt_amount__gt=0)
    if supplier_id:
        qs = qs.filter(supplier_id=supplier_id)
    return [(p.id, f'{p.purchase_number} (qarz: {p.debt_amount})') for p in qs.order_by('-date')[:30]]
