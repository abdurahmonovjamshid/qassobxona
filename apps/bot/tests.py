"""Bot oqimlarining eng xavfli qismini (savatcha ma'lumotidan haqiqiy
Purchase/Butchering/Sale yaratish va tegishli servisni chaqirish) test
qiladi. Telegram HTTP API'ga chiqib ketmasligi uchun
`telebot.apihelper._make_request` almashtiriladi (`unittest.mock.patch`) —
hech qanday real xabar yuborilmaydi. Har bir test o'zining vaqtinchalik test
bazasida ishlaydi (Django TestCase), production `db.sqlite3`ga tegmaydi."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.bot.handlers import butchering as butchering_handlers
from apps.bot.handlers import expenses as expense_handlers
from apps.bot.handlers import payments as payment_handlers
from apps.bot.handlers import purchases as purchase_handlers
from apps.bot.handlers import sales as sale_handlers
from apps.bot.models import TgUser
from apps.butchering.models import Butchering, ButcheringSpecification, ButcheringSpecificationItem
from apps.customers.models import Customer
from apps.expenses.models import Expense, ExpenseCategory
from apps.inventory.services import inventory_service
from apps.kassa.services import cash_service
from apps.payments.models import Payment
from apps.products.models import Product, ProductCategory
from apps.purchases.models import Purchase
from apps.sales.models import Sale
from apps.suppliers.models import Supplier


def _fake_call(chat_id=1):
    return SimpleNamespace(id='cb1', message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1))


def _fake_response(token, method_url, method='get', params=None, files=None):
    params = params or {}
    if method_url == 'sendMessage':
        return {'message_id': 1, 'date': 0, 'chat': {'id': params.get('chat_id'), 'type': 'private'}, 'text': params.get('text', '')}
    return True


@patch('telebot.apihelper._make_request')
class PurchaseFlowTests(TestCase):
    def setUp(self):
        category = ProductCategory.objects.create(name='Asosiy', code='ASOS')
        self.product = Product.objects.create(name='Lahm', code='LAHM', category=category, sale_price=Decimal('95000'))
        self.supplier = Supplier.objects.create(name='Ferma')
        self.tg_user = TgUser.objects.create(telegram_id=1, state='purchase.confirm', data={
            'supplier_id': self.supplier.id, 'supplier_name': self.supplier.name,
            'date': '2026-01-10',
            'items': [{
                'product_id': self.product.id, 'product_name': self.product.name,
                'net_weight': '420', 'price_per_kg': '78000', 'pieces': 1,
            }],
            'expenses': [{'expense_type': 'TRANSPORT', 'amount': '300000', 'notes': ''}],
            'paid_amount': '0', 'payment_type': '',
        })

    def test_confirm_creates_purchase_and_stock(self, mock_req):
        mock_req.side_effect = _fake_response
        purchase_handlers.confirm_purchase(_fake_call(), self.tg_user)

        purchase = Purchase.objects.get(supplier=self.supplier)
        self.assertEqual(purchase.status, Purchase.Status.CONFIRMED)
        self.assertEqual(purchase.total_amount, Decimal('420') * Decimal('78000'))
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('420'))
        # Landed cost = narx/kg + (transport / vazn) = 78000 + (300000/420).
        item = purchase.items.get()
        self.assertEqual(item.landed_unit_cost, (Decimal('78000') + Decimal('300000') / Decimal('420')).quantize(Decimal('0.01')))

        self.tg_user.refresh_from_db()
        self.assertEqual(self.tg_user.state, '')

    def test_confirm_with_payment_requires_cash_in_kassa(self, mock_req):
        """Naqd to'lov kassa balansidan oshsa, butun operatsiya (Purchase
        ham) rollback bolishi kerak — `record_cash_out`dagi haqiqiy biznes
        qoidasi (kassa manfiyga chiqmasin) botda ham amal qilishini
        tekshiradi."""
        mock_req.side_effect = _fake_response
        self.tg_user.data['paid_amount'] = '10000000'
        self.tg_user.data['payment_type'] = 'CASH'
        self.tg_user.save(update_fields=['data'])

        purchase_handlers.confirm_purchase(_fake_call(), self.tg_user)

        self.assertFalse(Purchase.objects.filter(supplier=self.supplier).exists())
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('0'))

    def test_confirm_with_payment_succeeds_when_kassa_funded(self, mock_req):
        from apps.kassa.services import cash_service
        cash_service.record_manual_balance(amount=Decimal('20000000'), date='2026-01-01')

        mock_req.side_effect = _fake_response
        self.tg_user.data['paid_amount'] = '10000000'
        self.tg_user.data['payment_type'] = 'CASH'
        self.tg_user.save(update_fields=['data'])

        purchase_handlers.confirm_purchase(_fake_call(), self.tg_user)

        purchase = Purchase.objects.get(supplier=self.supplier)
        self.assertEqual(purchase.paid_amount, Decimal('10000000'))
        self.assertEqual(purchase.debt_amount, purchase.total_amount - Decimal('10000000'))
        self.assertEqual(cash_service.get_balance(), Decimal('20000000') - Decimal('10000000'))


@patch('telebot.apihelper._make_request')
class SaleFlowTests(TestCase):
    def setUp(self):
        category = ProductCategory.objects.create(name='Asosiy', code='ASOS')
        self.product = Product.objects.create(name='Lahm', code='LAHM', category=category, sale_price=Decimal('95000'))
        self.customer = Customer.objects.create(name='Ali aka')
        inventory_service.stock_in(
            product=self.product, quantity=Decimal('10'), movement_type='PURCHASE',
            unit_cost=Decimal('78000'), date='2026-01-01',
        )
        self.tg_user = TgUser.objects.create(telegram_id=2, state='sale.confirm', data={
            'customer_id': self.customer.id, 'customer_name': self.customer.name,
            'date': '2026-01-10', 'due_date': None,
            'items': [{
                'product_id': self.product.id, 'product_name': self.product.name,
                'quantity': '5', 'price': '95000', 'discount': '0', 'pieces': 0,
            }],
            'paid_amount': '0', 'payment_type': '',
        })

    def test_confirm_creates_sale_and_reduces_stock(self, mock_req):
        mock_req.side_effect = _fake_response
        sale_handlers.confirm_sale(_fake_call(), self.tg_user)

        sale = Sale.objects.get(customer=self.customer)
        self.assertEqual(sale.status, Sale.Status.CONFIRMED)
        self.assertEqual(sale.total_amount, Decimal('5') * Decimal('95000'))
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('5'))

    def test_confirm_rejects_oversell(self, mock_req):
        mock_req.side_effect = _fake_response
        self.tg_user.data['items'][0]['quantity'] = '999'
        self.tg_user.save(update_fields=['data'])

        sale_handlers.confirm_sale(_fake_call(), self.tg_user)

        self.assertFalse(Sale.objects.filter(customer=self.customer).exists())
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('10'))


@patch('telebot.apihelper._make_request')
class ButcheringFlowTests(TestCase):
    def setUp(self):
        category = ProductCategory.objects.create(name='Asosiy', code='ASOS')
        self.whole = Product.objects.create(name='Mol (butun)', code='MOL', category=category)
        self.lahm = Product.objects.create(name='Lahm', code='LAHM', category=category, sale_price=Decimal('95000'))
        self.suyak = Product.objects.create(name='Suyak', code='SUYAK', category=category, sale_price=Decimal('20000'))
        spec = ButcheringSpecification.objects.create(name='Standart', parent_product=self.whole)
        ButcheringSpecificationItem.objects.create(specification=spec, child_product=self.lahm, cost_percentage=Decimal('70'))
        ButcheringSpecificationItem.objects.create(specification=spec, child_product=self.suyak, cost_percentage=Decimal('30'))

        inventory_service.stock_in(
            product=self.whole, quantity=Decimal('100'), movement_type='PURCHASE',
            unit_cost=Decimal('50000'), date='2026-01-01',
        )
        self.tg_user = TgUser.objects.create(telegram_id=3, state='butch.picking_output', data={
            'input_product_id': self.whole.id, 'input_product_name': self.whole.name,
            'input_weight': '100', 'input_pieces': 0,
            'specification_id': spec.id, 'date': '2026-01-10',
            'outputs': [
                {'product_id': self.lahm.id, 'product_name': self.lahm.name, 'quantity': '70', 'pieces': 0},
                {'product_id': self.suyak.id, 'product_name': self.suyak.name, 'quantity': '30', 'pieces': 0},
            ],
            'expenses': [],
        })

    def test_confirm_creates_butchering_and_moves_stock(self, mock_req):
        mock_req.side_effect = _fake_response
        butchering_handlers.confirm_butchering_cb(_fake_call(), self.tg_user)

        butchering = Butchering.objects.get(input_product=self.whole)
        self.assertEqual(butchering.status, Butchering.Status.CONFIRMED)
        self.assertEqual(butchering.output_weight, Decimal('100'))
        self.assertEqual(inventory_service.get_stock(self.whole), Decimal('0'))
        self.assertEqual(inventory_service.get_stock(self.lahm), Decimal('70'))
        self.assertEqual(inventory_service.get_stock(self.suyak), Decimal('30'))

        # Spetsifikatsiya % bo'yicha taqsimot: 100kg x 50000 = 5,000,000 jami;
        # Lahm 70% -> 3,500,000 / 70kg = 50,000/kg.
        lahm_output = butchering.outputs.get(product=self.lahm)
        self.assertEqual(lahm_output.unit_cost, Decimal('50000.00'))


@patch('telebot.apihelper._make_request')
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Ali aka')
        self.tg_user = TgUser.objects.create(telegram_id=4, state='pay.confirm', data={
            'party_type': 'customer', 'party_id': self.customer.id, 'party_name': self.customer.name,
            'doc_id': None, 'amount': '500000', 'payment_type': 'CASH',
            'date': '2026-01-10', 'notes': '',
        })

    def test_confirm_creates_payment_and_cash_in(self, mock_req):
        mock_req.side_effect = _fake_response
        payment_handlers.confirm_payment(_fake_call(), self.tg_user)

        payment = Payment.objects.get(customer=self.customer)
        self.assertEqual(payment.amount, Decimal('500000'))
        # Mijozdan naqd to'lov -> kassaga KIRIM (chiqim emas), balans oshadi.
        self.assertEqual(cash_service.get_balance(), Decimal('500000'))

    def test_cancel_deletes_payment_and_reverses_cash(self, mock_req):
        mock_req.side_effect = _fake_response
        payment_handlers.confirm_payment(_fake_call(), self.tg_user)
        payment = Payment.objects.get(customer=self.customer)

        call = _fake_call()
        call.data = f'paycancel:{payment.pk}'
        payment_handlers.cancel_payment_cb(call, self.tg_user)

        self.assertFalse(Payment.objects.filter(pk=payment.pk).exists())
        self.assertEqual(cash_service.get_balance(), Decimal('0'))


@patch('telebot.apihelper._make_request')
class ExpenseFlowTests(TestCase):
    def setUp(self):
        cash_service.record_manual_balance(amount=Decimal('1000000'), date='2026-01-01')
        self.category = ExpenseCategory.objects.create(name='Transport')
        self.tg_user = TgUser.objects.create(telegram_id=5, state='expense.confirm', data={
            'category_id': self.category.id, 'category_name': self.category.name,
            'amount': '150000', 'payment_type': 'CASH', 'date': '2026-01-10', 'description': '',
        })

    def test_confirm_creates_expense_and_cash_out(self, mock_req):
        mock_req.side_effect = _fake_response
        expense_handlers.confirm_expense(_fake_call(), self.tg_user)

        expense = Expense.objects.get(category=self.category)
        self.assertEqual(expense.amount, Decimal('150000'))
        self.assertEqual(cash_service.get_balance(), Decimal('1000000') - Decimal('150000'))

    def test_confirm_rejects_when_kassa_insufficient(self, mock_req):
        mock_req.side_effect = _fake_response
        self.tg_user.data['amount'] = '999999999'
        self.tg_user.save(update_fields=['data'])

        expense_handlers.confirm_expense(_fake_call(), self.tg_user)

        self.assertFalse(Expense.objects.filter(category=self.category).exists())
        self.assertEqual(cash_service.get_balance(), Decimal('1000000'))
