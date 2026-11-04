from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook, load_workbook

from apps.inventory.models import InventoryCount, InventoryCountItem
from apps.inventory.services import excel_service, inventory_service
from apps.products.models import Product, ProductCategory


def _make_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(excel_service.HEADER)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


class ConfirmInventoryCountCostTests(TestCase):
    """`confirm_inventory_count` — unit_cost berilganda tannarxni ham
    qayta belgilash (to'liq chiqim + qayta kirim) rejimini tekshiradi."""

    def setUp(self):
        category = ProductCategory.objects.create(name='Go‘sht', code='meat')
        self.product = Product.objects.create(name='Lahm', code='LAHM', category=category)
        inventory_service.stock_in(
            product=self.product, quantity=Decimal('100'), movement_type='PURCHASE',
            unit_cost=Decimal('50000'), date=timezone.localdate(),
        )

    def _confirm(self, counted_kg, counted_pieces, unit_cost):
        count = InventoryCount.objects.create(date=timezone.localdate())
        item = InventoryCountItem.objects.create(
            count=count, product=self.product, counted_kg=counted_kg,
            counted_pieces=counted_pieces, unit_cost=unit_cost,
        )
        inventory_service.confirm_inventory_count(count)
        return count, item

    def test_diff_only_when_unit_cost_blank_preserves_average(self):
        self._confirm(Decimal('95'), 0, None)
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('95'))
        self.assertEqual(inventory_service.get_weighted_average_cost(self.product), Decimal('50000.00'))

    def test_unit_cost_provided_replaces_average(self):
        self._confirm(Decimal('95'), 2, Decimal('55000'))
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('95'))
        self.assertEqual(inventory_service.get_stock_pieces(self.product), 2)
        # Butun qoldiq chiqim qilinib yangi tannarx bilan qayta kirim qilingani
        # uchun o'rtacha tannarx aynan yangi qiymatga teng bo'ladi.
        self.assertEqual(inventory_service.get_weighted_average_cost(self.product), Decimal('55000.00'))


class MovingAverageCostTests(TestCase):
    """Sotilib ketgan partiya keyingi xarid tannarxiga ta'sir qilmasligi kerak."""

    def setUp(self):
        category = ProductCategory.objects.create(name='Go‘sht', code='meat')
        self.product = Product.objects.create(name='Lahm', code='LAHM', category=category)
        self.today = timezone.localdate()

    def _in(self, qty, cost):
        inventory_service.stock_in(
            product=self.product, quantity=Decimal(qty), movement_type='PURCHASE',
            unit_cost=Decimal(cost), date=self.today,
        )

    def _out(self, qty):
        inventory_service.stock_out(
            product=self.product, quantity=Decimal(qty), movement_type='SALE',
            unit_cost=inventory_service.get_weighted_average_cost(self.product), date=self.today,
        )

    def test_sold_out_batch_does_not_affect_next_purchase(self):
        self._in('100', '70000')
        self._out('100')
        self._in('100', '60000')
        self.assertEqual(inventory_service.get_weighted_average_cost(self.product), Decimal('60000.00'))

    def test_partial_sale_keeps_average_of_remaining(self):
        self._in('100', '70000')
        self._out('50')
        self._in('50', '60000')
        # Qolgan 50 kg 70 000 + yangi 50 kg 60 000 -> 65 000
        self.assertEqual(inventory_service.get_weighted_average_cost(self.product), Decimal('65000.00'))

    def test_empty_stock_has_zero_cost(self):
        self._in('10', '70000')
        self._out('10')
        self.assertEqual(inventory_service.get_weighted_average_cost(self.product), Decimal('0'))


class StockTransferTests(TestCase):
    def setUp(self):
        from apps.inventory.models import Warehouse
        category = ProductCategory.objects.create(name='Go‘sht', code='meat')
        self.product = Product.objects.create(name='Lahm', code='LAHM', category=category)
        self.main = Warehouse.get_default()
        self.second, _ = Warehouse.objects.get_or_create(name='2-sklad')
        inventory_service.stock_in(
            product=self.product, quantity=Decimal('100'), pieces=4, movement_type='PURCHASE',
            unit_cost=Decimal('70000'), date=timezone.localdate(),
        )

    def _transfer(self, qty, pieces=0):
        from apps.inventory.models import StockTransfer, StockTransferItem
        transfer = StockTransfer.objects.create(
            date=timezone.localdate(), from_warehouse=self.main, to_warehouse=self.second,
        )
        StockTransferItem.objects.create(transfer=transfer, product=self.product, quantity=Decimal(qty), pieces=pieces)
        return inventory_service.confirm_transfer(transfer)

    def test_transfer_moves_stock_and_keeps_cost(self):
        self._transfer('30', 1)
        self.assertEqual(inventory_service.get_stock(self.product, self.main), Decimal('70'))
        self.assertEqual(inventory_service.get_stock(self.product, self.second), Decimal('30'))
        self.assertEqual(inventory_service.get_stock_pieces(self.product, self.second), 1)
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('100'))
        self.assertEqual(inventory_service.get_weighted_average_cost(self.product), Decimal('70000.00'))

    def test_cannot_transfer_more_than_warehouse_stock(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._transfer('150')

    def test_sale_from_second_warehouse_checks_its_stock(self):
        from django.core.exceptions import ValidationError
        self._transfer('30')
        with self.assertRaises(ValidationError):
            inventory_service.stock_out(
                product=self.product, quantity=Decimal('40'), movement_type='SALE',
                date=timezone.localdate(), warehouse=self.second,
            )

    def test_cancel_transfer_returns_stock(self):
        transfer = self._transfer('30')
        inventory_service.cancel_transfer(transfer)
        self.assertEqual(inventory_service.get_stock(self.product, self.main), Decimal('100'))
        self.assertEqual(inventory_service.get_stock(self.product, self.second), Decimal('0'))


class InventoryExcelRoundTripTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='u1', password='pass12345')
        self.client.force_login(self.user)
        category = ProductCategory.objects.create(name='Go‘sht', code='meat')
        self.product = Product.objects.create(name='Lahm', code='LAHM', category=category)
        inventory_service.stock_in(
            product=self.product, quantity=Decimal('100'), movement_type='PURCHASE',
            unit_cost=Decimal('50000'), date=timezone.localdate(),
        )

    def test_export_contains_current_stock_row(self):
        response = self.client.get(reverse('inventory:export'))
        self.assertEqual(response.status_code, 200)
        wb = load_workbook(BytesIO(response.content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(rows[0], tuple(excel_service.HEADER))
        data_row = next(r for r in rows[1:] if r[0] == self.product.id)
        self.assertEqual(data_row[3], 100.0)
        self.assertEqual(data_row[5], 50000.0)

    def test_import_updates_stock_and_cost(self):
        content = _make_xlsx([[self.product.id, self.product.code, self.product.name, 95, 2, 55000]])
        upload = SimpleUploadedFile(
            'ombor.xlsx', content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response = self.client.post(reverse('inventory:import'), {'file': upload})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('95'))
        self.assertEqual(inventory_service.get_stock_pieces(self.product), 2)
        self.assertEqual(InventoryCount.objects.count(), 1)

    def test_import_leaves_cost_untouched_when_blank(self):
        content = _make_xlsx([[self.product.id, self.product.code, self.product.name, 80, 0, None]])
        upload = SimpleUploadedFile('ombor.xlsx', content)
        self.client.post(reverse('inventory:import'), {'file': upload})
        self.assertEqual(inventory_service.get_stock(self.product), Decimal('80'))
        self.assertEqual(inventory_service.get_weighted_average_cost(self.product), Decimal('50000.00'))

    def test_import_rejects_unknown_product_id(self):
        content = _make_xlsx([[999999, 'XXX', 'Yoq mahsulot', 10, 0, 1000]])
        upload = SimpleUploadedFile('ombor.xlsx', content)
        response = self.client.post(reverse('inventory:import'), {'file': upload}, follow=True)
        self.assertEqual(InventoryCount.objects.count(), 0)
        messages = list(response.context['messages'])
        self.assertTrue(any('topilmadi' in str(m) for m in messages))

    def test_import_rejects_negative_kg(self):
        content = _make_xlsx([[self.product.id, self.product.code, self.product.name, -5, 0, 1000]])
        upload = SimpleUploadedFile('ombor.xlsx', content)
        response = self.client.post(reverse('inventory:import'), {'file': upload}, follow=True)
        self.assertEqual(InventoryCount.objects.count(), 0)
        messages = list(response.context['messages'])
        self.assertTrue(any('manfiy' in str(m) for m in messages))

    def test_import_rejects_wrong_header(self):
        wb = Workbook()
        ws = wb.active
        ws.append(['Wrong', 'Header'])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        upload = SimpleUploadedFile('bad.xlsx', buf.read())
        response = self.client.post(reverse('inventory:import'), {'file': upload}, follow=True)
        self.assertEqual(InventoryCount.objects.count(), 0)
        messages = list(response.context['messages'])
        self.assertTrue(any('sarlavhasi' in str(m) for m in messages))
