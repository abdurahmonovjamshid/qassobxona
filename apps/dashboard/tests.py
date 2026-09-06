from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.customers.models import Customer
from apps.products.models import Product, ProductCategory
from apps.suppliers.models import Supplier


class DashboardDebtorCreditorTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='u1', password='pass12345')
        self.client.force_login(user)

    def test_debitor_and_creditor_include_opening_balances(self):
        Customer.objects.create(name='Ali aka', opening_balance=Decimal('500000'))
        Supplier.objects.create(name='Abdulloh fermer', opening_balance=Decimal('12760000'))

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.context['debitor_total'], Decimal('500000'))
        self.assertEqual(response.context['creditor_total'], Decimal('12760000'))


class ResetBusinessDataCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='owner', password='pass12345')
        self.category = ProductCategory.objects.create(name='Go‘sht', code='meat')
        self.product = Product.objects.create(name='Lahm', code='LAHM', category=self.category)
        self.customer = Customer.objects.create(name='Ali aka', opening_balance=Decimal('500000'))
        self.supplier = Supplier.objects.create(name='Abdulloh fermer', opening_balance=Decimal('1000000'))

    def test_dry_run_deletes_nothing(self):
        out = StringIO()
        call_command('reset_business_data', stdout=out)

        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        self.assertTrue(Supplier.objects.filter(pk=self.supplier.pk).exists())
        self.assertIn('Jami:', out.getvalue())

    def test_yes_wipes_business_data_but_keeps_users(self):
        out = StringIO()
        call_command('reset_business_data', '--yes', '--no-backup', stdout=out)

        self.assertFalse(Product.objects.exists())
        self.assertFalse(ProductCategory.objects.exists())
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(Supplier.objects.exists())
        # Login hisobi tegilmagan bo'lishi kerak.
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_already_empty_reports_success_without_error(self):
        # Avval tozalab, keyin yana ishga tushirsak, xatosiz "bo'sh" deb aytishi kerak.
        call_command('reset_business_data', '--yes', '--no-backup', stdout=StringIO())
        out = StringIO()
        call_command('reset_business_data', '--yes', '--no-backup', stdout=out)
        self.assertIn("bo'sh", out.getvalue())
