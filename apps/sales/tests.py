from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.customers.models import Customer
from apps.sales.models import Sale
from apps.sales.services import sale_service


class DueSalesTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Ali aka')
        self.today = timezone.localdate()

    def _make_sale(self, number, *, status, debt, due_date):
        return Sale.objects.create(
            customer=self.customer, sale_number=number, date=self.today,
            due_date=due_date, status=status,
            total_amount=Decimal('100000'), paid_amount=Decimal('100000') - debt,
        )

    def test_includes_overdue_confirmed_sale_with_debt(self):
        sale = self._make_sale(
            'S-1', status=Sale.Status.CONFIRMED, debt=Decimal('20000'),
            due_date=self.today - timedelta(days=2),
        )
        self.assertIn(sale, sale_service.get_due_sales())

    def test_includes_sale_due_today(self):
        sale = self._make_sale(
            'S-2', status=Sale.Status.CONFIRMED, debt=Decimal('20000'), due_date=self.today,
        )
        self.assertIn(sale, sale_service.get_due_sales())

    def test_excludes_fully_paid_sale(self):
        sale = self._make_sale(
            'S-3', status=Sale.Status.CONFIRMED, debt=Decimal('0'),
            due_date=self.today - timedelta(days=2),
        )
        self.assertNotIn(sale, sale_service.get_due_sales())

    def test_excludes_sale_without_due_date(self):
        sale = self._make_sale(
            'S-4', status=Sale.Status.CONFIRMED, debt=Decimal('20000'), due_date=None,
        )
        self.assertNotIn(sale, sale_service.get_due_sales())

    def test_excludes_future_due_date(self):
        sale = self._make_sale(
            'S-5', status=Sale.Status.CONFIRMED, debt=Decimal('20000'),
            due_date=self.today + timedelta(days=2),
        )
        self.assertNotIn(sale, sale_service.get_due_sales())

    def test_excludes_draft_and_cancelled_sales(self):
        draft = self._make_sale(
            'S-6', status=Sale.Status.DRAFT, debt=Decimal('20000'),
            due_date=self.today - timedelta(days=1),
        )
        cancelled = self._make_sale(
            'S-7', status=Sale.Status.CANCELLED, debt=Decimal('20000'),
            due_date=self.today - timedelta(days=1),
        )
        due_sales = sale_service.get_due_sales()
        self.assertNotIn(draft, due_sales)
        self.assertNotIn(cancelled, due_sales)
