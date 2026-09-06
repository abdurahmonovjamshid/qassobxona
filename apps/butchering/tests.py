from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.butchering.forms import ButcheringSpecificationItemFormSet
from apps.butchering.models import (
    Butchering, ButcheringOutput, ButcheringSpecification, ButcheringSpecificationItem,
)
from apps.butchering.services import butchering_service
from apps.inventory.services import inventory_service
from apps.products.models import Product, ProductCategory
from apps.purchases.models import Purchase
from apps.suppliers.models import Supplier


class ButcheringCostAllocationTests(TestCase):
    def setUp(self):
        category = ProductCategory.objects.create(name='Go‘sht', code='meat')
        self.mol = Product.objects.create(name='Mol', code='MOL', category=category)
        self.lahm = Product.objects.create(name='Lahm', code='LAHM', category=category)
        self.suyak = Product.objects.create(name='Suyak', code='SUYAK', category=category)

        supplier = Supplier.objects.create(name='Abdulloh fermer')
        self.purchase = Purchase.objects.create(
            supplier=supplier, purchase_number='P-TEST-1', date=timezone.localdate(),
            total_amount=Decimal('32760000'), paid_amount=Decimal('0'),
        )

        # 100 kg Mol omborga 1000 so'm/kg tannarx bilan kiradi -> jami tannarx 100 000.
        inventory_service.stock_in(
            product=self.mol, quantity=Decimal('100'), movement_type='PURCHASE',
            unit_cost=Decimal('1000'), date=timezone.localdate(),
        )

    def _make_butchering(self, specification=None):
        butchering = Butchering.objects.create(
            purchase=self.purchase, input_product=self.mol, specification=specification,
            input_weight=Decimal('100'), date=timezone.localdate(),
        )
        # 80 kg Lahm + 20 kg Suyak = 100 kg og'irlik jihatidan teng bo'lmagan ulush.
        ButcheringOutput.objects.create(butchering=butchering, product=self.lahm, quantity=Decimal('80'))
        ButcheringOutput.objects.create(butchering=butchering, product=self.suyak, quantity=Decimal('20'))
        return butchering

    def test_weight_based_allocation_without_specification(self):
        butchering = self._make_butchering(specification=None)
        butchering_service.confirm_butchering(butchering)

        lahm_output = butchering.outputs.get(product=self.lahm)
        suyak_output = butchering.outputs.get(product=self.suyak)
        # Og'irlik ulushi: 80% -> 80000 / 80kg = 1000; 20% -> 20000 / 20kg = 1000.
        self.assertEqual(lahm_output.unit_cost, Decimal('1000.00'))
        self.assertEqual(suyak_output.unit_cost, Decimal('1000.00'))

    def test_percentage_based_allocation_shifts_cost_to_higher_value_output(self):
        spec = ButcheringSpecification.objects.create(name='Standart', parent_product=self.mol)
        ButcheringSpecificationItem.objects.create(
            specification=spec, child_product=self.lahm, cost_percentage=Decimal('60'),
        )
        ButcheringSpecificationItem.objects.create(
            specification=spec, child_product=self.suyak, cost_percentage=Decimal('40'),
        )

        butchering = self._make_butchering(specification=spec)
        butchering_service.confirm_butchering(butchering)

        lahm_output = butchering.outputs.get(product=self.lahm)
        suyak_output = butchering.outputs.get(product=self.suyak)
        # 60% ulush 80kg'ga taqsimlansa: 60000/80 = 750/kg (og'irlik ulushidan past,
        # chunki og'irligi ulushidan (80%) kamroq % berilgan, lekin son jihatidan
        # muhimi - suyakka nisbatan solishtirish).
        self.assertEqual(lahm_output.unit_cost, Decimal('750.00'))
        # 40% ulush 20kg'ga taqsimlansa: 40000/20 = 2000/kg.
        self.assertEqual(suyak_output.unit_cost, Decimal('2000.00'))
        # Muhimi: og'irlik-ulush variantiga (1000/1000) nisbatan taqsimot o'zgardi.
        self.assertNotEqual(lahm_output.unit_cost, suyak_output.unit_cost)

    def test_partial_percentage_falls_back_to_weight_based(self):
        spec = ButcheringSpecification.objects.create(name='Yarim to‘ldirilgan', parent_product=self.mol)
        ButcheringSpecificationItem.objects.create(
            specification=spec, child_product=self.lahm, cost_percentage=Decimal('60'),
        )
        ButcheringSpecificationItem.objects.create(
            specification=spec, child_product=self.suyak, cost_percentage=None,
        )

        butchering = self._make_butchering(specification=spec)
        butchering_service.confirm_butchering(butchering)

        lahm_output = butchering.outputs.get(product=self.lahm)
        suyak_output = butchering.outputs.get(product=self.suyak)
        self.assertEqual(lahm_output.unit_cost, Decimal('1000.00'))
        self.assertEqual(suyak_output.unit_cost, Decimal('1000.00'))


class ButcheringSpecificationFormsetValidationTests(TestCase):
    def setUp(self):
        category = ProductCategory.objects.create(name='Go‘sht', code='meat')
        self.mol = Product.objects.create(name='Mol', code='MOL2', category=category)
        self.lahm = Product.objects.create(name='Lahm', code='LAHM2', category=category)
        self.suyak = Product.objects.create(name='Suyak', code='SUYAK2', category=category)
        self.spec = ButcheringSpecification.objects.create(name='Standart', parent_product=self.mol)

    def _formset_data(self, pct_lahm, pct_suyak):
        return {
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-child_product': str(self.lahm.pk),
            'items-0-order': '0',
            'items-0-cost_percentage': pct_lahm,
            'items-1-child_product': str(self.suyak.pk),
            'items-1-order': '1',
            'items-1-cost_percentage': pct_suyak,
        }

    def test_valid_when_percentages_sum_to_100(self):
        formset = ButcheringSpecificationItemFormSet(
            self._formset_data('60', '40'), instance=self.spec, prefix='items',
        )
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_invalid_when_percentages_do_not_sum_to_100(self):
        formset = ButcheringSpecificationItemFormSet(
            self._formset_data('60', '30'), instance=self.spec, prefix='items',
        )
        self.assertFalse(formset.is_valid())

    def test_invalid_when_partially_filled(self):
        formset = ButcheringSpecificationItemFormSet(
            self._formset_data('60', ''), instance=self.spec, prefix='items',
        )
        self.assertFalse(formset.is_valid())

    def test_valid_when_all_blank(self):
        formset = ButcheringSpecificationItemFormSet(
            self._formset_data('', ''), instance=self.spec, prefix='items',
        )
        self.assertTrue(formset.is_valid(), formset.errors)
