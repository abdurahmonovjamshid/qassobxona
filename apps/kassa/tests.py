from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.kassa.models import CashTransaction
from apps.kassa.services import cash_service


class KassaAddBalanceViewTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username='admin', email='a@a.com', password='pass12345',
        )
        self.staff = get_user_model().objects.create_user(username='cashier', password='pass12345')

    def _post(self, **overrides):
        data = {'amount': '5000000', 'date': str(timezone.localdate()), 'notes': "Boshlang'ich naqd"}
        data.update(overrides)
        return self.client.post(reverse('kassa:add_balance'), data)

    def test_superuser_can_add_opening_balance(self):
        self.client.force_login(self.superuser)
        self._post()
        self.assertEqual(cash_service.get_balance(), Decimal('5000000'))
        txn = CashTransaction.objects.get()
        self.assertEqual(txn.transaction_type, CashTransaction.TransactionType.OPENING)

    def test_non_superuser_cannot_add_balance(self):
        self.client.force_login(self.staff)
        self._post()
        self.assertEqual(cash_service.get_balance(), Decimal('0'))

    def test_zero_amount_rejected(self):
        self.client.force_login(self.superuser)
        self._post(amount='0')
        self.assertEqual(cash_service.get_balance(), Decimal('0'))


class CashRegisterTests(TestCase):
    """Naqd va Karta kassa alohida hisoblanadi; har bir amal tanlangan kassaga yoziladi."""

    def setUp(self):
        from apps.kassa.models import CashRegister
        from apps.suppliers.models import Supplier
        self.cash = CashRegister.for_payment_type('CASH')
        self.card = CashRegister.for_payment_type('CARD')
        self.supplier = Supplier.objects.create(name='Ferma')

    def test_balances_are_separate(self):
        from apps.kassa.services import cash_service
        cash_service.record_manual_balance(amount=Decimal('100'), date=timezone.localdate(), register=self.card)
        self.assertEqual(cash_service.get_balance(self.card), Decimal('100'))
        self.assertEqual(cash_service.get_balance(), Decimal('0'))
        self.assertEqual([b['register'].code for b in cash_service.get_balances()], ['CASH', 'CARD'])

    def test_card_out_checks_card_balance(self):
        from django.core.exceptions import ValidationError
        from apps.kassa.services import cash_service
        from apps.payments.services import payment_service
        cash_service.record_manual_balance(amount=Decimal('1000'), date=timezone.localdate(), register=self.cash)
        with self.assertRaises(ValidationError):
            payment_service.create_payment(
                amount=Decimal('500'), date=timezone.localdate(), supplier=self.supplier, cash_register=self.card,
            )

    def test_cancel_payment_reverses_into_same_kassa(self):
        from apps.kassa.services import cash_service
        from apps.payments.services import payment_service
        payment = payment_service.create_payment(
            amount=Decimal('300'), date=timezone.localdate(), customer=self._customer(), cash_register=self.card,
        )
        self.assertEqual(cash_service.get_balance(self.card), Decimal('300'))
        payment_service.delete_payment(payment)
        self.assertEqual(cash_service.get_balance(self.card), Decimal('0'))
        self.assertEqual(cash_service.get_balance(self.cash), Decimal('0'))

    def test_default_payment_goes_to_cash(self):
        from apps.kassa.services import cash_service
        from apps.payments.services import payment_service
        payment = payment_service.create_payment(amount=Decimal('50'), date=timezone.localdate(), customer=self._customer())
        self.assertEqual(payment.cash_register, self.cash)
        self.assertEqual(cash_service.get_balance(self.cash), Decimal('50'))

    def test_expense_from_card(self):
        from apps.expenses.models import ExpenseCategory
        from apps.expenses.services import create_expense
        from apps.kassa.services import cash_service
        cash_service.record_manual_balance(amount=Decimal('200'), date=timezone.localdate(), register=self.card)
        expense = create_expense(
            category=ExpenseCategory.objects.create(name='Svet'), amount=Decimal('80'),
            date=timezone.localdate(), cash_register=self.card,
        )
        self.assertEqual(expense.payment_type, 'CARD')
        self.assertEqual(cash_service.get_balance(self.card), Decimal('120'))

    def _customer(self):
        from apps.customers.models import Customer
        return Customer.objects.create(name='Ali aka')


class KassaNotesTests(TestCase):
    def test_kassa_page_shows_payment_and_expense_notes(self):
        from apps.customers.models import Customer
        from apps.expenses.models import ExpenseCategory
        from apps.expenses.services import create_expense
        from apps.payments.services import payment_service
        user = get_user_model().objects.create_user(username='k', password='pass12345')
        self.client.force_login(user)
        customer = Customer.objects.create(name='Ali aka')
        payment = payment_service.create_payment(
            amount=Decimal('500'), date=timezone.localdate(), customer=customer, notes="Avans uchun",
        )
        create_expense(category=ExpenseCategory.objects.create(name='Svet'), amount=Decimal('100'),
                       date=timezone.localdate(), description='Noyabr svet puli')
        payment_service.delete_payment(payment)
        payment_service.create_payment(amount=Decimal('50'), date=timezone.localdate(), customer=customer)

        content = self.client.get(reverse('kassa:detail')).content.decode()
        self.assertEqual(content.count('Avans uchun'), 2)  # to'lov va uning bekor qilinishi
        self.assertIn('Noyabr svet puli', content)
        self.assertIn('Ali aka', content)


class KassaCounterpartyAndExportTests(TestCase):
    def setUp(self):
        from apps.customers.models import Customer
        from apps.expenses.models import ExpenseCategory
        from apps.expenses.services import create_expense
        from apps.payments.services import payment_service
        from apps.suppliers.models import Supplier
        self.client.force_login(get_user_model().objects.create_user(username='k', password='pass12345'))
        today = timezone.localdate()
        payment_service.create_payment(amount=Decimal('900'), date=today, customer=Customer.objects.create(name='Ali aka'))
        payment_service.create_payment(amount=Decimal('200'), date=today, supplier=Supplier.objects.create(name='Chori bula'))
        create_expense(category=ExpenseCategory.objects.create(name='Svet'), amount=Decimal('100'),
                       date=today, description='Noyabr svet puli')

    def test_kassa_page_shows_customer_and_supplier_column(self):
        content = self.client.get(reverse('kassa:detail')).content.decode()
        self.assertIn('Mijoz / Yetkazib beruvchi', content)
        self.assertIn('Ali aka', content)
        self.assertIn('Chori bula', content)
        self.assertIn('Yetkazib beruvchi</div>', content)

    def _sheet(self, response):
        from io import BytesIO
        from openpyxl import load_workbook
        self.assertEqual(response.status_code, 200)
        self.assertIn('.xlsx', response['Content-Disposition'])
        return [list(r) for r in load_workbook(BytesIO(response.content)).active.iter_rows(values_only=True)]

    def test_kassa_export(self):
        rows = self._sheet(self.client.get(reverse('kassa:export')))
        self.assertEqual(rows[0][3], 'Mijoz / Yetkazib beruvchi')
        by_party = {r[3]: r for r in rows[1:] if r[3]}
        self.assertEqual(by_party['Ali aka'][4], 'Mijoz')
        self.assertEqual(by_party['Ali aka'][6], 900)
        self.assertEqual(by_party['Chori bula'][7], 200)
        expense = next(r for r in rows[1:] if r[5] == 'Svet')
        self.assertEqual(expense[9], 'Noyabr svet puli')

    def test_expense_export(self):
        rows = self._sheet(self.client.get(reverse('expenses:export')))
        self.assertEqual(rows[0], ['Sana', 'Kategoriya', 'Kassa', 'Izoh', 'Summa'])
        self.assertEqual(rows[1][1:], ['Svet', 'Naqd kassa', 'Noyabr svet puli', 100])
        self.assertEqual(rows[-1][3:], ['Jami', 100])
