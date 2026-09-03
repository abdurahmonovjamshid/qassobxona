"""Bazani tozalab, so'nggi ~35 kunlik real ko'rinishdagi namunaviy ma'lumot bilan to'ldiradi.

Ishlatilishi:
    python manage.py seed_demo_data

Faqat biznes ma'lumotlari (Product, Supplier, Customer, Purchase, Butchering,
Sale, Payment, Expense va h.k.) tozalanadi. Foydalanuvchi hisoblari (User),
sessiyalar va migratsiya tarixi tegilmaydi.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.butchering.models import Butchering, ButcheringOutput
from apps.butchering.services import butchering_service
from apps.customers.models import Customer
from apps.expenses.models import Expense, ExpenseCategory
from apps.inventory.models import StockMovement
from apps.inventory.services import inventory_service
from apps.payments.models import Payment
from apps.payments.services import payment_service
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseExpense
from apps.purchases.services import purchase_service
from apps.sales.models import Sale, SaleItem
from apps.sales.services import sale_service
from apps.suppliers.models import Supplier

# Bo'laklashda har bir mahsulotning nisbiy ulushi (TZ 12-bo'lim misolidagi
# 420 kg -> Lahm 150, Qovurg'a 45, Son 65, Kurak 50, Bo'yin 25, Qiyma 30,
# Suyak 35, Yog' 15, Chiqit 5 nisbatlariga asoslangan; ulushlar yig'indisi
# aniq 1.0). Haqiqiy chiqim YIELD_FACTOR bilan pasaytirilib, dumaloqlash
# sabab output > input bo'lib qolish xavfi oldini oladi.
OUTPUT_RATIOS = [
    ('LAHM', Decimal('150') / Decimal('420')),
    ('QOVURGA', Decimal('45') / Decimal('420')),
    ('SON', Decimal('65') / Decimal('420')),
    ('KURAK', Decimal('50') / Decimal('420')),
    ('BOYIN', Decimal('25') / Decimal('420')),
    ('QIYMA', Decimal('30') / Decimal('420')),
    ('SUYAK', Decimal('35') / Decimal('420')),
    ('YOG', Decimal('15') / Decimal('420')),
    ('CHIQIT', Decimal('5') / Decimal('420')),
]
YIELD_FACTOR = Decimal('0.95')

# Sotuv narxlari xarid narxidan (butun hayvon, ~70-75k/kg) sezilarli yuqori
# qo'yilgan — aks holda bo'laklash orqali qo'shilgan qiymat (butun hayvonni
# qimmatroq bo'laklarga ajratish foydasi) real biznesdagidek aks etmaydi.
PRODUCTS = [
    ('Mol (butun)', 'MOL-BUTUN', Product.Category.WHOLE, Decimal('0')),
    ('Lahm', 'LAHM', Product.Category.MEAT, Decimal('110000')),
    ('Son', 'SON', Product.Category.MEAT, Decimal('100000')),
    ('Kurak', 'KURAK', Product.Category.MEAT, Decimal('95000')),
    ("Qovurg'a", 'QOVURGA', Product.Category.MEAT, Decimal('90000')),
    ("Bo'yin", 'BOYIN', Product.Category.MEAT, Decimal('85000')),
    ('Qiyma', 'QIYMA', Product.Category.MEAT, Decimal('98000')),
    ('Suyak', 'SUYAK', Product.Category.BONE, Decimal('30000')),
    ("Yog'", 'YOG', Product.Category.FAT, Decimal('40000')),
    ('Chiqit', 'CHIQIT', Product.Category.WASTE, Decimal('8000')),
]

SUPPLIERS = [
    ("Abdulloh fermer xo'jaligi", '+998 90 123 45 67', 'Samarqand vil., Payariq t.'),
    ('Jamshid Abdurahmonov', '+998 91 234 56 78', "Qashqadaryo vil., Kitob t."),
    ('Qishloq chorva fermasi', '+998 93 345 67 89', "Jizzax vil., Zomin t."),
]

CUSTOMERS = [
    ('Ali aka', '+998 90 111 22 33', Decimal('5000000')),
    ('Bahodir market', '+998 91 222 33 44', Decimal('10000000')),
    ('Sardor oshxona', '+998 93 333 44 55', Decimal('8000000')),
    ('Gulnora opa', '+998 94 444 55 66', Decimal('2000000')),
    ('Rustam savdo', '+998 95 555 66 77', Decimal('6000000')),
]

EXPENSE_CATEGORIES = [
    'Transport', 'Ijara', 'Elektr', 'Suv', 'Ish haqi', 'Qadoqlash', 'Kommunal', 'Boshqa',
]


class Command(BaseCommand):
    help = "Bazani tozalab, real ko'rinishdagi eski sanali namunaviy ma'lumot bilan to'ldiradi."

    def handle(self, *args, **options):
        random.seed(42)
        user = User.objects.filter(is_superuser=True, is_active=True).order_by('id').first()
        if not user:
            self.stderr.write(self.style.ERROR('Avval kamida bitta superuser yarating (createsuperuser).'))
            return

        with transaction.atomic():
            self._wipe_business_data()
            products = self._create_products()
            suppliers = self._create_suppliers()
            customers = self._create_customers()
            self._create_expense_categories()

            today = timezone.localdate()
            purchase_days = [today - timedelta(days=d) for d in (34, 27, 20, 13, 6)]

            purchase_seq = 1
            for i, pdate in enumerate(purchase_days):
                purchase = self._create_purchase(purchase_seq, pdate, suppliers, products, user)
                purchase_seq += 1
                self._create_butchering(purchase, products, user)
                self._sell_random_days(
                    products, customers, user,
                    start=pdate + timedelta(days=1),
                    end=(purchase_days[i + 1] - timedelta(days=1)) if i + 1 < len(purchase_days) else today,
                )

            self._create_expenses(user, start=today - timedelta(days=34), end=today)

        self.stdout.write(self.style.SUCCESS('Namunaviy ma\'lumotlar muvaffaqiyatli yaratildi.'))
        self.stdout.write(f"  Suppliers: {Supplier.objects.count()}")
        self.stdout.write(f"  Customers: {Customer.objects.count()}")
        self.stdout.write(f"  Products: {Product.objects.count()}")
        self.stdout.write(f"  Purchases: {Purchase.objects.count()} (confirmed)")
        self.stdout.write(f"  Butcherings: {Butchering.objects.count()} (confirmed)")
        self.stdout.write(f"  Sales: {Sale.objects.count()} (confirmed)")
        self.stdout.write(f"  Payments: {Payment.objects.count()}")
        self.stdout.write(f"  Expenses: {Expense.objects.count()}")

    def _wipe_business_data(self):
        Payment.objects.all().delete()
        StockMovement.objects.all().delete()
        SaleItem.objects.all().delete()
        Sale.objects.all().delete()
        ButcheringOutput.objects.all().delete()
        Butchering.objects.all().delete()
        PurchaseExpense.objects.all().delete()
        Purchase.objects.all().delete()
        Expense.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        Product.objects.all().delete()
        Customer.objects.all().delete()
        Supplier.objects.all().delete()

    def _create_products(self):
        products = {}
        for name, code, category, price in PRODUCTS:
            products[code] = Product.objects.create(
                name=name, code=code, category=category, sale_price=price,
            )
        return products

    def _create_suppliers(self):
        return [
            Supplier.objects.create(name=name, phone=phone, address=address)
            for name, phone, address in SUPPLIERS
        ]

    def _create_customers(self):
        return [
            Customer.objects.create(name=name, phone=phone, credit_limit=limit)
            for name, phone, limit in CUSTOMERS
        ]

    def _create_expense_categories(self):
        return [ExpenseCategory.objects.create(name=name) for name in EXPENSE_CATEGORIES]

    def _create_purchase(self, seq, pdate, suppliers, products, user):
        supplier = random.choice(suppliers)
        gross_weight = Decimal(random.randint(430, 470))
        net_weight = gross_weight - Decimal(random.randint(10, 20))
        price_per_kg = Decimal(random.randint(68, 74)) * 1000

        purchase = Purchase(
            supplier=supplier,
            product=products['MOL-BUTUN'],
            purchase_number=f"P{pdate.strftime('%Y%m%d')}-{seq:04d}",
            date=pdate,
            animal_type='Mol',
            gross_weight=gross_weight,
            net_weight=net_weight,
            price_per_kg=price_per_kg,
            status=Purchase.Status.DRAFT,
            created_by=user,
        )
        purchase.save()

        PurchaseExpense.objects.create(
            purchase=purchase, expense_type=PurchaseExpense.ExpenseType.TRANSPORT,
            amount=Decimal(random.randint(200, 350)) * 1000,
        )

        purchase_service.confirm_purchase(purchase, user=user)

        paid_ratio = Decimal(random.choice(['0.5', '0.6', '0.7', '0.85', '1.0']))
        paid_amount = (purchase.total_amount * paid_ratio).quantize(Decimal('1'))
        if paid_amount > 0:
            payment_service.create_payment(
                amount=paid_amount, payment_type='CASH', date=pdate,
                supplier=supplier, purchase=purchase, user=user,
            )
        return purchase

    def _create_butchering(self, purchase, products, user):
        butchering = Butchering(
            purchase=purchase,
            input_product=products['MOL-BUTUN'],
            input_weight=purchase.net_weight,
            date=purchase.date,
            status=Butchering.Status.DRAFT,
            created_by=user,
        )
        butchering.save()

        for code, ratio in OUTPUT_RATIOS:
            qty = (purchase.net_weight * ratio * YIELD_FACTOR).quantize(Decimal('0.001'))
            if qty > 0:
                ButcheringOutput.objects.create(butchering=butchering, product=products[code], quantity=qty)

        butchering_service.confirm_butchering(butchering, user=user)
        return butchering

    def _sell_random_days(self, products, customers, user, *, start, end):
        sellable = [p for code, p in products.items() if code != 'MOL-BUTUN']
        day = start
        sale_seq = Sale.objects.count() + 1
        while day <= end:
            if random.random() < 0.85:
                num_sales = random.randint(1, 3)
                for _ in range(num_sales):
                    sale = self._create_sale(sale_seq, day, customers, sellable, user)
                    if sale:
                        sale_seq += 1
            day += timedelta(days=1)

    def _create_sale(self, seq, day, customers, sellable, user):
        customer = random.choice(customers)
        sale = Sale(
            customer=customer,
            sale_number=f"S{day.strftime('%Y%m%d')}-{seq:04d}",
            date=day,
            status=Sale.Status.DRAFT,
            created_by=user,
        )
        sale.save()

        items_count = random.randint(1, 3)
        chosen_products = random.sample(sellable, k=min(items_count, len(sellable)))
        created_any = False
        for product in chosen_products:
            available = inventory_service.get_stock(product)
            if available <= Decimal('0.5'):
                continue
            qty = min(available, Decimal(random.uniform(1.5, 8)).quantize(Decimal('0.001')))
            if qty <= 0:
                continue
            variance = Decimal(random.choice(['0.95', '1.0', '1.0', '1.05']))
            price = (product.sale_price * variance).quantize(Decimal('1'))
            discount = Decimal(random.choice([0, 0, 0, 5000, 10000]))
            SaleItem.objects.create(sale=sale, product=product, quantity=qty, price=price, discount=discount)
            created_any = True

        if not created_any:
            sale.delete()
            return None

        sale_service.confirm_sale(sale, user=user)

        paid_ratio = Decimal(random.choice(['0.4', '0.6', '0.8', '1.0', '1.0']))
        paid_amount = (sale.total_amount * paid_ratio).quantize(Decimal('1'))
        if paid_amount > 0:
            payment_service.create_payment(
                amount=paid_amount, payment_type=random.choice(['CASH', 'CARD', 'TRANSFER']),
                date=day, customer=customer, sale=sale, user=user,
            )
        return sale

    def _create_expenses(self, user, *, start, end):
        by_name = {c.name: c for c in ExpenseCategory.objects.all()}

        # Ijara/ish haqi kabi doimiy (oylik) xarajatlar — kunlik tasodifiy
        # ehtimollik bilan emas, davr boshida bir martalik yoziladi, aks
        # holda 35 kunda bir necha marta takrorlanib xarajatni sun'iy
        # shishirib yuboradi.
        Expense.objects.create(
            category=by_name['Ijara'], amount=Decimal('1800000'),
            date=start, payment_type='TRANSFER', created_by=user,
        )
        Expense.objects.create(
            category=by_name['Ish haqi'], amount=Decimal('2200000'),
            date=start, payment_type='CASH', created_by=user,
        )

        variable_categories = [by_name[n] for n in ('Transport', 'Elektr', 'Suv', 'Qadoqlash', 'Kommunal', 'Boshqa')]
        amounts = {
            'Transport': (100000, 250000), 'Elektr': (250000, 450000), 'Suv': (40000, 90000),
            'Qadoqlash': (60000, 150000), 'Kommunal': (80000, 180000), 'Boshqa': (20000, 100000),
        }
        day = start
        while day <= end:
            if random.random() < 0.2:
                category = random.choice(variable_categories)
                lo, hi = amounts[category.name]
                Expense.objects.create(
                    category=category, amount=Decimal(random.randint(lo, hi)),
                    date=day, payment_type='CASH', created_by=user,
                )
            day += timedelta(days=1)
