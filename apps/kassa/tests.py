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
