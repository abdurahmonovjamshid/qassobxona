"""Bazani butunlay tozalab, ~2 oylik (o'tgan oy + shu oy) real ko'rinishdagi
namunaviy ma'lumot bilan qayta to'ldiradi — Mol va Qo'y kategoriyalari uchun
mahsulot, spetsifikatsiya, xarid, sotuv, bo'laklash, xarajatlar, to'lovlar,
kassa va inventarizatsiya amallarini o'z ichiga oladi. Dashboard/hisobotlarni
shaxsan ko'rib chiqish uchun mo'ljallangan.

Ishlatilishi:
    python manage.py seed_demo_data

Ishlaydigan joyi: faqat ORM va mavjud servis funksiyalaridan foydalanadi —
lokal ham, deploy qilingan (PythonAnywhere) muhitda ham bir xil ishlaydi.

Faqat biznes ma'lumotlari tozalanadi. Foydalanuvchi hisoblari (User),
sessiyalar va migratsiya tarixi tegilmaydi.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.butchering.models import (
    Butchering, ButcheringExpense, ButcheringOutput,
    ButcheringSpecification, ButcheringSpecificationItem,
)
from apps.butchering.services import butchering_service
from apps.customers.models import Customer
from apps.expenses.models import Expense, ExpenseCategory
from apps.inventory.models import InventoryCount, InventoryCountItem, StockMovement
from apps.inventory.services import inventory_service
from apps.kassa.models import CashTransaction
from apps.payments.models import Payment
from apps.payments.services import payment_service
from apps.products.models import Product, ProductCategory
from apps.purchases.models import Purchase, PurchaseExpense, PurchaseItem
from apps.purchases.services import purchase_service
from apps.sales.models import Sale, SaleItem
from apps.sales.services import sale_service
from apps.suppliers.models import Supplier

CATEGORY_NAMES = {
    'WHOLE': "Butun chorva",
    'BEEF': "Mol go'shti",
    'LAMB': "Qo'y go'shti",
    'FAT': "Yog'",
    'BONE': 'Suyak',
    'WASTE': 'Chiqit',
    'OTHER': 'Boshqa',
}

PRODUCTS = [
    ('Mol (butun)', 'MOL-BUTUN', 'WHOLE', Decimal('0')),
    ('Lahm', 'LAHM', 'BEEF', Decimal('110000')),
    ('Son', 'SON', 'BEEF', Decimal('100000')),
    ('Kurak', 'KURAK', 'BEEF', Decimal('95000')),
    ("Qovurg'a", 'QOVURGA', 'BEEF', Decimal('90000')),
    ("Bo'yin", 'BOYIN', 'BEEF', Decimal('85000')),
    ('Qiyma', 'QIYMA', 'BEEF', Decimal('98000')),
    ('Suyak', 'SUYAK', 'BONE', Decimal('30000')),
    ("Yog'", 'YOG', 'FAT', Decimal('40000')),
    ('Chiqit', 'CHIQIT', 'WASTE', Decimal('8000')),
    ("Qo'y (butun)", 'QOY-BUTUN', 'WHOLE', Decimal('0')),
    ("Qo'y lahm", 'QOY-LAHM', 'LAMB', Decimal('130000')),
    ("Qo'y qovurg'a", 'QOY-QOVURGA', 'LAMB', Decimal('125000')),
    ("Qo'y boldir", 'QOY-BOLDIR', 'LAMB', Decimal('100000')),
    ("Qo'y kuyruq yog'i", 'QOY-YOG', 'LAMB', Decimal('75000')),
]

# Bo'laklash spetsifikatsiyalari: father mahsulot -> (usul nomi, child mahsulot kodlari, ulush)
BEEF_SPEC = ("Standart mol bo'laklash", [
    ('LAHM', Decimal('150') / Decimal('420')),
    ('QOVURGA', Decimal('45') / Decimal('420')),
    ('SON', Decimal('65') / Decimal('420')),
    ('KURAK', Decimal('50') / Decimal('420')),
    ('BOYIN', Decimal('25') / Decimal('420')),
    ('QIYMA', Decimal('30') / Decimal('420')),
    ('SUYAK', Decimal('35') / Decimal('420')),
    ('YOG', Decimal('15') / Decimal('420')),
    ('CHIQIT', Decimal('5') / Decimal('420')),
])
LAMB_SPEC = ("Standart qo'y bo'laklash", [
    ('QOY-LAHM', Decimal('45') / Decimal('100')),
    ('QOY-QOVURGA', Decimal('20') / Decimal('100')),
    ('QOY-BOLDIR', Decimal('20') / Decimal('100')),
    ('QOY-YOG', Decimal('10') / Decimal('100')),
])
SPECIFICATIONS = {
    'MOL-BUTUN': BEEF_SPEC,
    'QOY-BUTUN': LAMB_SPEC,
}
YIELD_FACTOR = Decimal('0.95')

SUPPLIERS = [
    ("Abdulloh fermer xo'jaligi", '+998 90 123 45 67', 'Samarqand vil., Payariq t.', Decimal('0')),
    ('Jamshid Abdurahmonov', '+998 91 234 56 78', "Qashqadaryo vil., Kitob t.", Decimal('1500000')),
    ('Qishloq chorva fermasi', '+998 93 345 67 89', "Jizzax vil., Zomin t.", Decimal('0')),
]

# (nomi, telefon, kredit limit, boshlang'ich saldo, yetkazib beruvchi ham)
CUSTOMERS = [
    ('Ali aka', '+998 90 111 22 33', Decimal('5000000'), Decimal('0'), False),
    ('Bahodir market', '+998 91 222 33 44', Decimal('10000000'), Decimal('2000000'), True),
    ('Sardor oshxona', '+998 93 333 44 55', Decimal('8000000'), Decimal('0'), False),
    ('Gulnora opa', '+998 94 444 55 66', Decimal('2000000'), Decimal('0'), False),
    ('Rustam savdo', '+998 95 555 66 77', Decimal('6000000'), Decimal('500000'), False),
]

EXPENSE_CATEGORIES = [
    'Transport', 'Ijara', 'Elektr', 'Suv', 'Ish haqi', 'Qadoqlash', 'Kommunal', 'Boshqa',
]

# Bugundan necha kun oldin xarid qilinishi (~2 oylik davr — o'tgan oy + shu oy)
PURCHASE_DAY_OFFSETS = [65, 54, 43, 32, 21, 12, 5]

OPENING_CASH_BALANCE = Decimal('300000000')


class Command(BaseCommand):
    help = "Bazani tozalab, Mol/Qo'y kategoriyalari bo'yicha ~2 oylik to'liq amaliyot (xarid/sotuv/bo'laklash/xarajat/inventarizatsiya) bilan qayta to'ldiradi."

    def handle(self, *args, **options):
        random.seed(42)
        user = User.objects.filter(is_superuser=True, is_active=True).order_by('id').first()
        if not user:
            self.stderr.write(self.style.ERROR('Avval kamida bitta superuser yarating (createsuperuser).'))
            return

        today = timezone.localdate()
        start_date = today - timedelta(days=max(PURCHASE_DAY_OFFSETS) + 3)

        with transaction.atomic():
            self._wipe_business_data()
            products = self._create_products()
            specs = self._create_specifications(products)
            suppliers = self._create_suppliers()
            customers = self._create_customers()
            self._create_expense_categories()

            CashTransaction.objects.create(
                amount=OPENING_CASH_BALANCE, transaction_type=CashTransaction.TransactionType.OPENING,
                date=start_date, notes="Boshlang'ich kassa balansi (namunaviy)", created_by=user,
            )

            purchase_days = [today - timedelta(days=d) for d in PURCHASE_DAY_OFFSETS]
            purchase_seq = 1
            for i, pdate in enumerate(purchase_days):
                purchase = self._create_purchase(purchase_seq, pdate, suppliers, products, user)
                purchase_seq += 1
                sellable_from_this_batch = self._butcher_purchase(purchase, products, specs, user)

                self._sell_random_days(
                    sellable_from_this_batch, customers, user,
                    start=pdate + timedelta(days=1),
                    end=(purchase_days[i + 1] - timedelta(days=1)) if i + 1 < len(purchase_days) else today,
                )

            self._create_expenses(user, start=start_date, end=today)
            self._create_inventory_count(products, user, date=today)

        self.stdout.write(self.style.SUCCESS("Namunaviy ma'lumotlar muvaffaqiyatli yaratildi."))
        self.stdout.write(f"  Davr: {start_date} — {today}")
        self.stdout.write(f"  Kategoriyalar: {ProductCategory.objects.count()}")
        self.stdout.write(f"  Mahsulotlar: {Product.objects.count()}")
        self.stdout.write(f"  Bo'laklash spetsifikatsiyalari: {ButcheringSpecification.objects.count()}")
        self.stdout.write(f"  Suppliers: {Supplier.objects.count()}")
        self.stdout.write(f"  Customers: {Customer.objects.count()} (shundan hamkor: {Customer.objects.filter(is_supplier=True).count()})")
        self.stdout.write(f"  Xaridlar: {Purchase.objects.count()} (tasdiqlangan)")
        self.stdout.write(f"  Bo'laklashlar: {Butchering.objects.count()} (tasdiqlangan)")
        self.stdout.write(f"  Sotuvlar: {Sale.objects.count()} (tasdiqlangan)")
        self.stdout.write(f"  To'lovlar: {Payment.objects.count()}")
        self.stdout.write(f"  Xarajatlar: {Expense.objects.count()}")
        self.stdout.write(f"  Inventarizatsiyalar: {InventoryCount.objects.count()}")
        self.stdout.write(f"  Kassa balansi: {self._kassa_balance()} so'm")

    def _kassa_balance(self):
        from apps.kassa.services import cash_service
        return cash_service.get_balance()

    # ------------------------------------------------------------------ #
    # Tozalash
    # ------------------------------------------------------------------ #
    def _wipe_business_data(self):
        Payment.objects.all().delete()
        CashTransaction.objects.all().delete()
        StockMovement.objects.all().delete()
        InventoryCountItem.objects.all().delete()
        InventoryCount.objects.all().delete()
        SaleItem.objects.all().delete()
        Sale.objects.all().delete()
        ButcheringExpense.objects.all().delete()
        ButcheringOutput.objects.all().delete()
        Butchering.objects.all().delete()
        ButcheringSpecificationItem.objects.all().delete()
        ButcheringSpecification.objects.all().delete()
        PurchaseExpense.objects.all().delete()
        Purchase.objects.all().delete()
        Expense.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        Product.objects.all().delete()
        ProductCategory.objects.all().delete()
        Customer.objects.all().delete()
        Supplier.objects.all().delete()

    # ------------------------------------------------------------------ #
    # Kataloglar
    # ------------------------------------------------------------------ #
    def _create_products(self):
        categories = {
            code: ProductCategory.objects.get_or_create(code=code, defaults={'name': name})[0]
            for code, name in CATEGORY_NAMES.items()
        }
        products = {}
        for name, code, category_code, price in PRODUCTS:
            products[code] = Product.objects.create(
                name=name, code=code, category=categories[category_code], sale_price=price,
            )
        return products

    def _create_specifications(self, products):
        specs = {}
        for parent_code, (spec_name, ratios) in SPECIFICATIONS.items():
            spec = ButcheringSpecification.objects.create(
                name=spec_name, parent_product=products[parent_code], active=True,
            )
            for order, (child_code, _ratio) in enumerate(ratios):
                ButcheringSpecificationItem.objects.create(
                    specification=spec, child_product=products[child_code], order=order,
                )
            specs[parent_code] = {'spec': spec, 'ratios': ratios}
        return specs

    def _create_suppliers(self):
        return [
            Supplier.objects.create(name=name, phone=phone, address=address, opening_balance=opening)
            for name, phone, address, opening in SUPPLIERS
        ]

    def _create_customers(self):
        customers = []
        for name, phone, limit, opening, is_supplier in CUSTOMERS:
            customer = Customer.objects.create(
                name=name, phone=phone, credit_limit=limit, opening_balance=opening,
                is_supplier=is_supplier,
            )
            if is_supplier:
                linked = Supplier.objects.create(name=name, phone=phone)
                customer.linked_supplier = linked
                customer.save(update_fields=['linked_supplier'])
            customers.append(customer)
        return customers

    def _create_expense_categories(self):
        return [ExpenseCategory.objects.create(name=name) for name in EXPENSE_CATEGORIES]

    # ------------------------------------------------------------------ #
    # Xarid (ko'p mahsulotli: mol + qo'y)
    # ------------------------------------------------------------------ #
    def _create_purchase(self, seq, pdate, suppliers, products, user):
        supplier = random.choice(suppliers)
        purchase = Purchase(
            supplier=supplier,
            purchase_number=f"P{pdate.strftime('%Y%m%d')}-{seq:04d}",
            date=pdate,
            status=Purchase.Status.DRAFT,
            created_by=user,
        )
        purchase.save()

        # Har doim mol, ehtimollik bilan qo'y ham xarid qilinadi — ko'p
        # mahsulotli xarid (bir nechta PurchaseItem) sinovdan o'tishi uchun.
        cow_net_weight = Decimal(random.randint(410, 460))
        cow_price = Decimal(random.randint(68, 74)) * 1000
        PurchaseItem.objects.create(
            purchase=purchase, product=products['MOL-BUTUN'],
            net_weight=cow_net_weight, pieces=1, price_per_kg=cow_price,
        )

        if random.random() < 0.7:
            sheep_count = random.randint(1, 3)
            sheep_net_weight = Decimal(random.randint(18, 26) * sheep_count)
            sheep_price = Decimal(random.randint(58, 65)) * 1000
            PurchaseItem.objects.create(
                purchase=purchase, product=products['QOY-BUTUN'],
                net_weight=sheep_net_weight, pieces=sheep_count, price_per_kg=sheep_price,
            )

        PurchaseExpense.objects.create(
            purchase=purchase, expense_type=PurchaseExpense.ExpenseType.TRANSPORT,
            amount=Decimal(random.randint(200, 350)) * 1000,
        )
        PurchaseExpense.objects.create(
            purchase=purchase, expense_type=PurchaseExpense.ExpenseType.SLAUGHTER,
            amount=Decimal(random.randint(150, 300)) * 1000,
        )

        purchase_service.confirm_purchase(purchase, user=user)

        paid_ratio = Decimal(random.choice(['0.5', '0.6', '0.7', '0.85', '1.0']))
        paid_amount = (purchase.total_amount * paid_ratio).quantize(Decimal('1'))
        if paid_amount > 0:
            payment_service.create_payment(
                amount=paid_amount, payment_type=random.choice(['CASH', 'CASH', 'TRANSFER']), date=pdate,
                supplier=supplier, purchase=purchase, user=user,
            )
        return purchase

    # ------------------------------------------------------------------ #
    # Bo'laklash (spetsifikatsiya bo'yicha, qo'shimcha xarajat bilan)
    # ------------------------------------------------------------------ #
    def _butcher_purchase(self, purchase, products, specs, user):
        sellable = []
        for item in purchase.items.select_related('product').all():
            parent_code = item.product.code
            if parent_code not in specs:
                continue
            spec_info = specs[parent_code]
            butchering = Butchering(
                purchase=purchase,
                input_product=item.product,
                specification=spec_info['spec'],
                input_weight=item.net_weight,
                input_pieces=item.pieces,
                date=purchase.date,
                status=Butchering.Status.DRAFT,
                created_by=user,
            )
            butchering.save()

            outputs = []
            for code, ratio in spec_info['ratios']:
                qty = (item.net_weight * ratio * YIELD_FACTOR).quantize(Decimal('0.001'))
                if qty <= 0:
                    continue
                pieces = max(1, round(float(qty) / random.uniform(2, 4)))
                out = ButcheringOutput.objects.create(
                    butchering=butchering, product=products[code], quantity=qty, pieces=pieces,
                )
                outputs.append(out)
                sellable.append(products[code])

            ButcheringExpense.objects.create(
                butchering=butchering, expense_type=ButcheringExpense.ExpenseType.LABOR,
                amount=Decimal(random.randint(40, 90)) * 1000,
            )

            butchering_service.confirm_butchering(butchering, user=user)
        return list({p.code: p for p in sellable}.values())

    # ------------------------------------------------------------------ #
    # Sotuv (kg + dona)
    # ------------------------------------------------------------------ #
    def _sell_random_days(self, sellable, customers, user, *, start, end):
        if not sellable or start > end:
            return
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
            available_pieces = inventory_service.get_stock_pieces(product)
            pieces = min(available_pieces, random.randint(1, 3))
            variance = Decimal(random.choice(['0.95', '1.0', '1.0', '1.05']))
            price = (product.sale_price * variance).quantize(Decimal('1'))
            discount = Decimal(random.choice([0, 0, 0, 5000, 10000]))
            SaleItem.objects.create(
                sale=sale, product=product, quantity=qty, pieces=pieces, price=price, discount=discount,
            )
            created_any = True

        if not created_any:
            sale.delete()
            return None

        sale_service.confirm_sale(sale, user=user)

        paid_ratio = Decimal(random.choice(['0.4', '0.6', '0.8', '1.0', '1.0']))
        paid_amount = (sale.total_amount * paid_ratio).quantize(Decimal('1'))
        if paid_amount > 0:
            payment_service.create_payment(
                amount=paid_amount, payment_type=random.choice(['CASH', 'CASH', 'CARD', 'TRANSFER']),
                date=day, customer=customer, sale=sale, user=user,
            )
        return sale

    # ------------------------------------------------------------------ #
    # Xarajatlar
    # ------------------------------------------------------------------ #
    def _create_expenses(self, user, *, start, end):
        by_name = {c.name: c for c in ExpenseCategory.objects.all()}

        # Ijara/ish haqi kabi doimiy (oylik) xarajatlar — har ikkala oy
        # boshida bir martadan yoziladi, kunlik tasodifiy ehtimollik bilan emas.
        month_starts = set()
        d = start
        while d <= end:
            month_starts.add(d.replace(day=1) if d.day <= 5 else None)
            d += timedelta(days=1)
        month_starts.discard(None)
        if not month_starts:
            month_starts = {start}
        for month_start in sorted(month_starts):
            actual_date = max(month_start, start)
            Expense.objects.create(
                category=by_name['Ijara'], amount=Decimal('1800000'),
                date=actual_date, payment_type='TRANSFER', created_by=user,
            )
            Expense.objects.create(
                category=by_name['Ish haqi'], amount=Decimal('2200000'),
                date=actual_date, payment_type='CASH', created_by=user,
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

    # ------------------------------------------------------------------ #
    # Inventarizatsiya
    # ------------------------------------------------------------------ #
    def _create_inventory_count(self, products, user, *, date):
        candidates = [products['LAHM'], products['SUYAK']]
        count = InventoryCount(date=date, notes="Oylik inventarizatsiya (namunaviy)",
                                status=InventoryCount.Status.DRAFT, created_by=user)
        count.save()

        has_items = False
        for product, kg_delta, pieces_delta in zip(candidates, [Decimal('-1.5'), Decimal('0')], [0, 1]):
            system_kg = inventory_service.get_stock(product)
            system_pieces = inventory_service.get_stock_pieces(product)
            counted_kg = max(Decimal('0'), system_kg + kg_delta)
            counted_pieces = max(0, system_pieces + pieces_delta)
            InventoryCountItem.objects.create(
                count=count, product=product, counted_kg=counted_kg, counted_pieces=counted_pieces,
            )
            has_items = True

        if has_items:
            inventory_service.confirm_inventory_count(count, user=user)
        else:
            count.delete()
