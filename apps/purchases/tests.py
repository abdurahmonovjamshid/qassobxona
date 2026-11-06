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

    def _fund(self, code='CASH', amount='5000000'):
        from apps.kassa.models import CashRegister
        from apps.kassa.services import cash_service
        register = CashRegister.for_payment_type(code)
        cash_service.record_manual_balance(amount=Decimal(amount), date=timezone.localdate(), register=register)
        return register

    def test_create_purchase_confirms_immediately(self):
        self._fund()
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
            reverse('purchases:create'), self._post_data(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Purchase.objects.exists())
        messages = list(response.context['messages'])
        self.assertTrue(any("Naqd kassada yetarli mablag'" in str(m) for m in messages))

    def test_card_payment_goes_to_card_kassa(self):
        from apps.kassa.services import cash_service
        card = self._fund('CARD', '1000000')
        response = self.client.post(
            reverse('purchases:create'), self._post_data(cash_register=str(card.pk)),
        )
        self.assertEqual(response.status_code, 302)
        payment = Purchase.objects.get().payments.get()
        self.assertEqual(payment.cash_register, card)
        self.assertEqual(payment.payment_type, 'CARD')
        self.assertEqual(cash_service.get_balance(card), Decimal('900000'))
        self.assertEqual(cash_service.get_balance(), Decimal('0'))

    def test_cash_payment_succeeds_after_kassa_opening_balance(self):
        from apps.kassa.services import cash_service

        cash_service.record_manual_balance(amount=Decimal('5000000'), date=timezone.localdate())

        response = self.client.post(
            reverse('purchases:create'), self._post_data(),
        )
        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.status, Purchase.Status.CONFIRMED)
        self.assertEqual(purchase.paid_amount, Decimal('100000'))
