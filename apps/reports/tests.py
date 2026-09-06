from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.customers.models import Customer
from apps.reports.services import statement_service
from apps.sales.models import Sale
from apps.suppliers.models import Supplier


class PartnerStatementFromSupplierTests(TestCase):
    """"Bolta" ssenariysi: bir shaxs ham yetkazib beruvchi (boshlang'ich saldo
    bilan), ham mijoz (sotuv qilingan) sifatida bog'langan. Supplier tarafidan
    akt-sverkaga kirilganda ham ikkala tomon birlashgan holda ko'rinishi kerak."""

    def setUp(self):
        self.supplier = Supplier.objects.create(name='Bolta', opening_balance=Decimal('2000000'))
        self.customer = Customer.objects.create(
            name='Bolta', is_supplier=True, linked_supplier=self.supplier,
        )
        Sale.objects.create(
            customer=self.customer, sale_number='S-BOLTA-1', date=timezone.localdate(),
            status=Sale.Status.CONFIRMED, total_amount=Decimal('300000'), paid_amount=Decimal('0'),
        )

    def test_supplier_side_statement_includes_customer_sale(self):
        statement = statement_service.build_partner_statement_for_supplier(self.supplier)

        self.assertIsNotNone(statement['customer_statement'])
        self.assertEqual(statement['supplier_statement']['closing_balance'], Decimal('2000000'))
        self.assertEqual(statement['customer_statement']['closing_balance'], Decimal('300000'))
        # Xarid tomonida harakat yo'q (faqat boshlang'ich saldo), lekin sotuv
        # (customer tomoni) baribir birlashtirilgan qatorlarda ko'rinishi kerak.
        self.assertTrue(any(row['op'] == 'Sotuv S-BOLTA-1' and row['side'] == 'customer' for row in statement['rows']))

    def test_matches_customer_side_partner_statement(self):
        from_customer = statement_service.build_partner_statement(self.customer)
        from_supplier = statement_service.build_partner_statement_for_supplier(self.supplier)

        self.assertEqual(from_customer['net_balance'], from_supplier['net_balance'])

    def test_unlinked_supplier_has_no_customer_statement(self):
        lone_supplier = Supplier.objects.create(name='Yolgiz yetkazib beruvchi')
        statement = statement_service.build_partner_statement_for_supplier(lone_supplier)
        self.assertIsNone(statement['customer_statement'])
