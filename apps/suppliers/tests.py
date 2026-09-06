from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.payments.services import payment_service
from apps.purchases.models import Purchase
from apps.suppliers.models import Supplier


class SupplierDebtTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name='Abdulloh fermer', opening_balance=Decimal('12760000'))

    def test_opening_balance_counts_as_debt_with_no_purchases(self):
        self.assertEqual(self.supplier.get_total_debt(), Decimal('12760000'))

    def test_opening_balance_plus_purchase_debt(self):
        Purchase.objects.create(
            supplier=self.supplier, purchase_number='P-1', date=timezone.localdate(),
            status=Purchase.Status.CONFIRMED, total_amount=Decimal('1000000'), paid_amount=Decimal('0'),
        )
        self.assertEqual(self.supplier.get_total_debt(), Decimal('13760000'))

    def test_general_payment_not_tied_to_purchase_reduces_debt(self):
        # Kassa balansi tekshiruvidan chetlab o'tish uchun CASH emas, TRANSFER
        # to'lov turidan foydalaniladi (bu yerda tekshirilayotgan narsa — qarz
        # hisob-kitobi, kassa balansi emas).
        payment_service.create_payment(
            amount=Decimal('760000'), payment_type='TRANSFER', date=timezone.localdate(),
            supplier=self.supplier,
        )
        self.assertEqual(self.supplier.get_total_debt(), Decimal('12000000'))
