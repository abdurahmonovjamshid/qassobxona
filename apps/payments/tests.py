"""To'lov yo'nalishi (`Payment.direction`) testlari.

Asosiy biznes holati: mijoz perechislenie qilganda pul ba'zan to'g'ridan-to'g'ri
yetkazib beruvchining hisobiga tushadi. Bu ikkala qarzni ham kamaytiradi va
yetkazib beruvchida avans yig'ilishiga olib keladi; keyinchalik o'sha avans
undan naqd qaytarib olinadi."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.customers.models import Customer
from apps.kassa.services import cash_service
from apps.payments.models import Payment
from apps.payments.services import payment_service
from apps.purchases.models import Purchase
from apps.sales.models import Sale
from apps.suppliers.models import Supplier


class PaymentDirectionDefaultTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Dilshod')
        self.supplier = Supplier.objects.create(name='Abdulloh fermer')
        self.today = timezone.localdate()

    def test_customer_payment_defaults_to_incoming(self):
        payment = payment_service.create_payment(
            amount=Decimal('100000'), payment_type='TRANSFER', date=self.today,
            customer=self.customer,
        )
        self.assertEqual(payment.direction, Payment.Direction.IN)

    def test_supplier_payment_defaults_to_outgoing(self):
        payment = payment_service.create_payment(
            amount=Decimal('100000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier,
        )
        self.assertEqual(payment.direction, Payment.Direction.OUT)


class SupplierRefundTests(TestCase):
    """Yetkazib beruvchidan pul olish (avansni qaytarib olish)."""

    def setUp(self):
        self.supplier = Supplier.objects.create(name='Abdulloh fermer')
        self.today = timezone.localdate()
        Purchase.objects.create(
            supplier=self.supplier, purchase_number='P-1', date=self.today,
            status=Purchase.Status.CONFIRMED, total_amount=Decimal('1000000'),
            paid_amount=Decimal('0'),
        )

    def test_money_taken_from_supplier_increases_our_debt(self):
        payment_service.create_payment(
            amount=Decimal('1000000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier, direction=Payment.Direction.OUT,
        )
        self.assertEqual(self.supplier.get_total_debt(), Decimal('0'))

        payment_service.create_payment(
            amount=Decimal('300000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier, direction=Payment.Direction.IN,
        )
        # Undan 300 000 qaytarib olindi — demak unga yana shuncha qarzdormiz.
        self.assertEqual(self.supplier.get_total_debt(), Decimal('300000'))

    def test_cash_taken_from_supplier_increases_kassa(self):
        payment_service.create_payment(
            amount=Decimal('250000'), payment_type='CASH', date=self.today,
            supplier=self.supplier, direction=Payment.Direction.IN,
        )
        self.assertEqual(cash_service.get_balance(), Decimal('250000'))

    def test_deleting_incoming_supplier_payment_reverses_kassa_and_debt(self):
        payment = payment_service.create_payment(
            amount=Decimal('250000'), payment_type='CASH', date=self.today,
            supplier=self.supplier, direction=Payment.Direction.IN,
        )
        payment_service.delete_payment(payment)
        self.assertEqual(cash_service.get_balance(), Decimal('0'))
        self.assertEqual(self.supplier.get_total_debt(), Decimal('1000000'))

    def test_incoming_payment_tied_to_purchase_lowers_paid_amount(self):
        purchase = Purchase.objects.get(purchase_number='P-1')
        payment_service.create_payment(
            amount=Decimal('1000000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier, purchase=purchase, direction=Payment.Direction.OUT,
        )
        purchase.refresh_from_db()
        self.assertEqual(purchase.paid_amount, Decimal('1000000'))

        payment_service.create_payment(
            amount=Decimal('400000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier, purchase=purchase, direction=Payment.Direction.IN,
        )
        purchase.refresh_from_db()
        self.assertEqual(purchase.paid_amount, Decimal('600000'))
        self.assertEqual(purchase.debt_amount, Decimal('400000'))


class CustomerRefundTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Dilshod')
        self.today = timezone.localdate()
        Sale.objects.create(
            customer=self.customer, sale_number='S-1', date=self.today,
            status=Sale.Status.CONFIRMED, total_amount=Decimal('500000'),
            paid_amount=Decimal('0'),
        )

    def test_refund_to_customer_increases_his_debt(self):
        payment_service.create_payment(
            amount=Decimal('500000'), payment_type='TRANSFER', date=self.today,
            customer=self.customer, direction=Payment.Direction.IN,
        )
        self.assertEqual(self.customer.get_total_debt(), Decimal('0'))

        payment_service.create_payment(
            amount=Decimal('120000'), payment_type='TRANSFER', date=self.today,
            customer=self.customer, direction=Payment.Direction.OUT,
        )
        self.assertEqual(self.customer.get_total_debt(), Decimal('120000'))

    def test_cash_refund_to_customer_requires_kassa_balance(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            payment_service.create_payment(
                amount=Decimal('120000'), payment_type='CASH', date=self.today,
                customer=self.customer, direction=Payment.Direction.OUT,
            )


class ThreeWaySettlementTests(TestCase):
    """Mijoz pulni to'g'ridan-to'g'ri yetkazib beruvchining hisobiga
    o'tkazadi, keyin ortib qolgan avans undan naqd qaytarib olinadi."""

    def setUp(self):
        self.today = timezone.localdate()
        self.customer = Customer.objects.create(name='Dilshod')
        self.supplier = Supplier.objects.create(name='Abdulloh fermer')
        Sale.objects.create(
            customer=self.customer, sale_number='S-1', date=self.today,
            status=Sale.Status.CONFIRMED, total_amount=Decimal('5000000'),
            paid_amount=Decimal('0'),
        )
        Purchase.objects.create(
            supplier=self.supplier, purchase_number='P-1', date=self.today,
            status=Purchase.Status.CONFIRMED, total_amount=Decimal('3000000'),
            paid_amount=Decimal('0'),
        )

    def test_full_cycle(self):
        # 1. Mijoz 5 000 000 ni yetkazib beruvchining hisobiga o'tkazadi.
        #    Bu ikki yozuv bilan kiritiladi va kassaga tegmaydi.
        payment_service.create_payment(
            amount=Decimal('5000000'), payment_type='TRANSFER', date=self.today,
            customer=self.customer, direction=Payment.Direction.IN,
        )
        payment_service.create_payment(
            amount=Decimal('5000000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier, direction=Payment.Direction.OUT,
        )
        self.assertEqual(self.customer.get_total_debt(), Decimal('0'))
        # Yetkazib beruvchiga 3 000 000 qarz edik, 5 000 000 tushdi —
        # 2 000 000 avans qoldi (manfiy qarz).
        self.assertEqual(self.supplier.get_total_debt(), Decimal('-2000000'))
        self.assertEqual(cash_service.get_balance(), Decimal('0'))

        # 2. O'sha avansni undan naqd qaytarib olamiz.
        payment_service.create_payment(
            amount=Decimal('2000000'), payment_type='CASH', date=self.today,
            supplier=self.supplier, direction=Payment.Direction.IN,
        )
        self.assertEqual(self.supplier.get_total_debt(), Decimal('0'))
        self.assertEqual(cash_service.get_balance(), Decimal('2000000'))

    def test_statement_puts_refund_on_debit_side(self):
        from apps.reports.services import statement_service

        payment_service.create_payment(
            amount=Decimal('5000000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier, direction=Payment.Direction.OUT,
        )
        payment_service.create_payment(
            amount=Decimal('2000000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier, direction=Payment.Direction.IN,
        )
        statement = statement_service.build_supplier_statement(self.supplier)
        refund_rows = [r for r in statement['rows'] if r['category'] == 'Qaytarim']
        self.assertEqual(len(refund_rows), 1)
        self.assertEqual(refund_rows[0]['debit'], Decimal('2000000'))
        # Xarid 3 000 000, to'lov 5 000 000, qaytarim 2 000 000 -> saldo 0.
        self.assertEqual(statement['closing_balance'], Decimal('0'))


class CancelledDocumentPaymentTests(TestCase):
    """Bekor qilingan sotuv/xaridga bog'langan to'lov qarz hisobidan
    chiqariladi. Ilgari bu qoida faqat `get_total_debt()`da bor edi, shuning
    uchun akt-sverka va dashboard boshqa raqam ko'rsatardi."""

    def setUp(self):
        self.today = timezone.localdate()
        self.customer = Customer.objects.create(name='Dilshod')
        self.supplier = Supplier.objects.create(name='Abdulloh fermer')

        self.sale = Sale.objects.create(
            customer=self.customer, sale_number='S-1', date=self.today,
            status=Sale.Status.CONFIRMED, total_amount=Decimal('500000'),
            paid_amount=Decimal('0'),
        )
        payment_service.create_payment(
            amount=Decimal('500000'), payment_type='TRANSFER', date=self.today,
            customer=self.customer, sale=self.sale,
        )
        self.sale.status = Sale.Status.CANCELLED
        self.sale.save(update_fields=['status'])

        self.purchase = Purchase.objects.create(
            supplier=self.supplier, purchase_number='P-1', date=self.today,
            status=Purchase.Status.CONFIRMED, total_amount=Decimal('800000'),
            paid_amount=Decimal('0'),
        )
        payment_service.create_payment(
            amount=Decimal('800000'), payment_type='TRANSFER', date=self.today,
            supplier=self.supplier, purchase=self.purchase,
        )
        self.purchase.status = Purchase.Status.CANCELLED
        self.purchase.save(update_fields=['status'])

    def test_debt_ignores_cancelled_document_payments(self):
        self.assertEqual(self.customer.get_total_debt(), Decimal('0'))
        self.assertEqual(self.supplier.get_total_debt(), Decimal('0'))

    def test_customer_statement_matches_debt(self):
        from apps.reports.services import statement_service
        statement = statement_service.build_customer_statement(self.customer)
        self.assertEqual(statement['closing_balance'], self.customer.get_total_debt())
        self.assertEqual(statement['rows'], [])

    def test_supplier_statement_matches_debt(self):
        from apps.reports.services import statement_service
        statement = statement_service.build_supplier_statement(self.supplier)
        self.assertEqual(statement['closing_balance'], self.supplier.get_total_debt())
        self.assertEqual(statement['rows'], [])

    def test_dashboard_totals_match_debt(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        user = get_user_model().objects.create_user(username='kassir', password='pass12345')
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.context['debitor_total'], self.customer.get_total_debt())
        self.assertEqual(response.context['creditor_total'], self.supplier.get_total_debt())
