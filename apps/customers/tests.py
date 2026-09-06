from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.customers.models import Customer
from apps.payments.services import payment_service
from apps.sales.models import Sale


class CustomerDebtTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Ali aka', opening_balance=Decimal('500000'))

    def test_opening_balance_counts_as_debt_with_no_sales(self):
        self.assertEqual(self.customer.get_total_debt(), Decimal('500000'))

    def test_opening_balance_plus_sale_debt(self):
        Sale.objects.create(
            customer=self.customer, sale_number='S-1', date=timezone.localdate(),
            status=Sale.Status.CONFIRMED, total_amount=Decimal('200000'), paid_amount=Decimal('0'),
        )
        self.assertEqual(self.customer.get_total_debt(), Decimal('700000'))

    def test_general_payment_not_tied_to_sale_reduces_debt(self):
        # Mijoz avvaldan qarzdor (opening_balance) va shu qarzga to'lov qiladi —
        # bu to'lov aniq bir sotuvga bog'lanmagan (sale=None).
        payment_service.create_payment(
            amount=Decimal('300000'), payment_type='CASH', date=timezone.localdate(),
            customer=self.customer,
        )
        self.assertEqual(self.customer.get_total_debt(), Decimal('200000'))
