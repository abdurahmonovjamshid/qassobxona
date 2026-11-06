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
    if method_url == 'sendDocument':
        return {'message_id': 1, 'date': 0, 'chat': {'id': params.get('chat_id'), 'type': 'private'}}
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


def _recording_response():
    """`_make_request` o'rniga: yuborilgan chaqiruvlarni yozib boradi."""
    sent = []

    def _fake(token, method_url, method='get', params=None, files=None):
        sent.append({'method': method_url, 'params': params or {}, 'files': files or {}})
        return _fake_response(token, method_url, method, params, files)

    return sent, _fake


def _fake_message(text, telegram_id=1, chat_id=1, message_id=99):
    return SimpleNamespace(
        text=text,
        message_id=message_id,
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=telegram_id),
    )


BOT_USERNAME = 'qassobxona_test_bot'


@patch('telebot.apihelper._make_request')
class StatementFromNameLinkTests(TestCase):
    """Ro'yxatdagi ismning o'zi bosiladigan havola bo'ladi va bosilganda
    to'liq akt-sverka .xlsx fayl sifatida keladi. Buyruqning o'zi ko'rinmaydi
    — Telegram yuborgan `/start sup_12` xabari darhol o'chiriladi."""

    def setUp(self):
        from apps.bot import links
        # Username'ni Telegram'dan so'ramasligi uchun keshni oldindan to'ldiramiz.
        links._username_cache = BOT_USERNAME
        self.addCleanup(setattr, links, '_username_cache', None)

        self.tg_user = TgUser.objects.create(telegram_id=1)
        self.supplier = Supplier.objects.create(name='Abdulloh fermer')
        self.customer = Customer.objects.create(name='Ali aka', opening_balance=Decimal('250000'))
        Purchase.objects.create(
            supplier=self.supplier, purchase_number='P-1', date='2026-01-10',
            status=Purchase.Status.CONFIRMED, total_amount=Decimal('1000000'),
            paid_amount=Decimal('0'),
        )

    def _documents(self, sent):
        return [c for c in sent if c['method'] == 'sendDocument']

    def test_name_is_a_link_and_command_is_hidden(self, mock_req):
        from apps.bot.handlers import suppliers as supplier_handlers
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        supplier_handlers.list_suppliers(_fake_call(), self.tg_user)

        text = [c for c in sent if c['method'] == 'sendMessage'][-1]['params']['text']
        self.assertIn(
            f'<a href="https://t.me/{BOT_USERNAME}?start=sup_{self.supplier.id}">Abdulloh fermer</a>',
            text,
        )
        # Ochiq buyruq ham, tugmalar ham ko'rinmasligi kerak.
        self.assertNotIn(f'/sup_{self.supplier.id}', text)

    def test_tapping_name_sends_statement_and_deletes_command(self, mock_req):
        import io

        from openpyxl import load_workbook

        from apps.bot.handlers import common
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        common.on_text(_fake_message(f'/start sup_{self.supplier.id}'))

        docs = self._documents(sent)
        self.assertEqual(len(docs), 1)
        filename, content = docs[0]['files']['document']
        self.assertTrue(filename.endswith('.xlsx'))
        self.assertEqual(load_workbook(io.BytesIO(content)).sheetnames, ['Yetkazib beruvchi (xarid)'])
        # Foydalanuvchi nomidan yuborilgan texnik buyruq o'chirilgan bo'lishi kerak.
        self.assertTrue(any(c['method'] == 'deleteMessage' for c in sent))

    def test_customer_name_link_sends_statement(self, mock_req):
        from apps.bot.handlers import common
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        common.on_text(_fake_message(f'/start mij_{self.customer.id}'))

        self.assertEqual(len(self._documents(sent)), 1)

    def test_plain_command_still_works(self, mock_req):
        """Bot username'i noma'lum bo'lgan holat uchun zaxira ko'rinish."""
        from apps.bot.handlers import common
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        common.on_text(_fake_message(f'/sup_{self.supplier.id}'))

        self.assertEqual(len(self._documents(sent)), 1)

    def test_link_falls_back_to_plain_command_without_username(self, mock_req):
        from apps.bot import links
        from apps.bot.handlers import suppliers as supplier_handlers
        links._username_cache = ''
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        supplier_handlers.list_suppliers(_fake_call(), self.tg_user)

        text = [c for c in sent if c['method'] == 'sendMessage'][-1]['params']['text']
        self.assertNotIn('<a href', text)
        self.assertIn(f'/sup_{self.supplier.id}', text)

    def test_name_with_html_characters_is_escaped(self, mock_req):
        from apps.bot.handlers import suppliers as supplier_handlers
        Supplier.objects.create(name='Aka & Uka <Ferma>')
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        supplier_handlers.list_suppliers(_fake_call(), self.tg_user)

        text = [c for c in sent if c['method'] == 'sendMessage'][-1]['params']['text']
        self.assertIn('Aka &amp; Uka &lt;Ferma&gt;', text)

    def test_link_works_even_mid_conversation(self, mock_req):
        from apps.bot.handlers import common
        self.tg_user.state = 'pay.amount'
        self.tg_user.save(update_fields=['state'])
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        common.on_text(_fake_message(f'/start sup_{self.supplier.id}'))

        self.assertEqual(len(self._documents(sent)), 1)
        self.tg_user.refresh_from_db()
        self.assertEqual(self.tg_user.state, '')

    def test_plain_start_still_shows_menu(self, mock_req):
        """`/start` (parametrsiz) avvalgidek salomlashish xabarini berishi kerak."""
        from apps.bot.handlers import common
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        common.on_text(_fake_message('/start'))

        self.assertEqual(self._documents(sent), [])
        self.assertIn('Assalomu alaykum', sent[-1]['params']['text'])

    def test_unknown_id_replies_without_file(self, mock_req):
        from apps.bot.handlers import common
        sent, fake = _recording_response()
        mock_req.side_effect = fake

        common.on_text(_fake_message('/start sup_999999'))

        self.assertEqual(self._documents(sent), [])
        self.assertIn('topilmadi', sent[-1]['params']['text'])


@patch('telebot.apihelper._make_request')
class WarehouseFlowTests(TestCase):
    """Botda tanlangan ombor hujjatga yoziladi va qoldiq shu ombordan olinadi."""

    def setUp(self):
        from apps.inventory.models import Warehouse
        category = ProductCategory.objects.create(name='Asosiy', code='ASOS')
        self.product = Product.objects.create(name='Lahm', code='LAHM', category=category, sale_price=Decimal('95000'))
        self.customer = Customer.objects.create(name='Ali aka')
        self.main = Warehouse.get_default()
        self.second, _ = Warehouse.objects.get_or_create(name='2-sklad')
        inventory_service.stock_in(
            product=self.product, quantity=Decimal('10'), movement_type='PURCHASE',
            unit_cost=Decimal('78000'), date='2026-01-01', warehouse=self.second,
        )

    def _sale_user(self, warehouse, qty):
        return TgUser.objects.create(telegram_id=7, state='sale.confirm', data={
            'customer_id': self.customer.id, 'customer_name': self.customer.name,
            'warehouse_id': warehouse.id, 'warehouse_name': warehouse.name,
            'date': '2026-01-10', 'due_date': None,
            'items': [{
                'product_id': self.product.id, 'product_name': self.product.name,
                'quantity': qty, 'price': '95000', 'discount': '0', 'pieces': 0,
            }],
            'paid_amount': '0', 'payment_type': '',
        })

    def test_sale_from_selected_warehouse(self, mock_req):
        mock_req.side_effect = _fake_response
        sale_handlers.confirm_sale(_fake_call(), self._sale_user(self.second, '4'))
        sale = Sale.objects.get(customer=self.customer)
        self.assertEqual(sale.warehouse, self.second)
        self.assertEqual(inventory_service.get_stock(self.product, self.second), Decimal('6'))

    def test_sale_from_empty_warehouse_is_rejected(self, mock_req):
        mock_req.side_effect = _fake_response
        sale_handlers.confirm_sale(_fake_call(), self._sale_user(self.main, '4'))
        self.assertFalse(Sale.objects.filter(customer=self.customer).exists())
        self.assertEqual(inventory_service.get_stock(self.product, self.second), Decimal('10'))

    def test_product_picker_shows_selected_warehouse_stock(self, mock_req):
        from apps.bot import choices
        items = dict(choices.active_products_with_stock(self.second))
        self.assertIn('10', items[self.product.id])
        items = dict(choices.active_products_with_stock(self.main))
        self.assertIn('(0 kg)', items[self.product.id])

    def test_bot_transfer_moves_stock(self, mock_req):
        from apps.bot.handlers import inventory as inventory_handlers
        mock_req.side_effect = _fake_response
        tg_user = TgUser.objects.create(telegram_id=8, state='transfer.confirm', data={
            'from_warehouse_id': self.second.id, 'from_warehouse_name': self.second.name,
            'to_warehouse_id': self.main.id, 'to_warehouse_name': self.main.name,
            'date': '2026-01-10',
            'items': [{'product_id': self.product.id, 'product_name': self.product.name, 'quantity': '3', 'pieces': 0}],
        })
        inventory_handlers.confirm_transfer(_fake_call(), tg_user)
        self.assertEqual(inventory_service.get_stock(self.product, self.second), Decimal('7'))
        self.assertEqual(inventory_service.get_stock(self.product, self.main), Decimal('3'))
