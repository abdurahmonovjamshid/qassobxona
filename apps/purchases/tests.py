from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.products.models import Product, ProductCategory
from apps.purchases.models import Purchase
from apps.suppliers.models import Supplier


class PurchaseCreateViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='u1', password='pass12345')
        self.client.force_login(self.user)
        self.supplier = Supplier.objects.create(name='Abdulloh fermer')
        category = ProductCategory.objects.create(name='Go‘sht', code='meat')
        self.product = Product.objects.create(name='Mol', code='MOL', category=category)

    def _post_data(self, **overrides):
        data = {
            'supplier': str(self.supplier.id),
            'date': str(timezone.localdate()),
            'notes': '',
            'paid_amount': '100000',
            # TRANSFER emas CASH — bu test xaridni tasdiqlash oqimini tekshiradi,
            # kassa naqd balansiga bog'liq bo'lishi shart emas (bu alohida
            # apps.kassa.tests da tekshiriladi).
            'payment_type': 'TRANSFER',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-product': str(self.product.id),
            'items-0-net_weight': '100',
            'items-0-pieces': '1',
            'items-0-price_per_kg': '10000',
            'expenses-TOTAL_FORMS': '0',
            'expenses-INITIAL_FORMS': '0',
            'expenses-MIN_NUM_FORMS': '0',
            'expenses-MAX_NUM_FORMS': '1000',
        }
        data.update(overrides)
        return data

    def test_create_purchase_confirms_immediately(self):
        response = self.client.post(reverse('purchases:create'), self._post_data())
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['form'].errors)
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.status, Purchase.Status.CONFIRMED)
        self.assertEqual(purchase.total_amount, Decimal('1000000'))
        self.assertEqual(purchase.paid_amount, Decimal('100000'))

    def test_cash_payment_exceeding_kassa_balance_rolls_back_whole_purchase(self):
        # Kassada mablag' yo'q (yangi tizim) holatida naqd to'lov bilan xarid
        # yaratilsa — butun xarid (mahsulotlari bilan) saqlanmasligi kerak,
        # foydalanuvchiga esa aniq sabab ko'rsatilishi kerak.
        response = self.client.post(
            reverse('purchases:create'), self._post_data(payment_type='CASH'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Purchase.objects.exists())
        messages = list(response.context['messages'])
        self.assertTrue(any("Kassada yetarli mablag'" in str(m) for m in messages))

    def test_cash_payment_succeeds_after_kassa_opening_balance(self):
        from apps.kassa.services import cash_service

        cash_service.record_manual_balance(amount=Decimal('5000000'), date=timezone.localdate())

        response = self.client.post(
            reverse('purchases:create'), self._post_data(payment_type='CASH'),
        )
        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.status, Purchase.Status.CONFIRMED)
        self.assertEqual(purchase.paid_amount, Decimal('100000'))
