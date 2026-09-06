"""Barcha biznes ma'lumotlarini butunlay o'chirib, bazani nol holatga
qaytaradi — real biznesga o'tishdan oldin bir martalik ishlatish uchun.

O'chiriladi: xaridlar, sotuvlar, bo'laklashlar, to'lovlar, ombor harakatlari,
kassa, xarajatlar, mijoz/yetkazib beruvchilar, mahsulotlar va bo'laklash
retseptlari (spetsifikatsiyalar).

O'CHIRILMAYDI: foydalanuvchi (login) hisoblari, guruh/ruxsatlar, sessiyalar,
migratsiya tarixi.

Ishlatilishi:
    python manage.py reset_business_data          # faqat nechta yozuv borligini ko'rsatadi (hech narsa o'chmaydi)
    python manage.py reset_business_data --yes     # haqiqatan o'chiradi

SQLite ishlatilganda (mahalliy yoki PythonAnywhere) komanda ishga
tushirishdan oldin avtomatik ravishda `db.sqlite3.bak-<vaqt>` nomli zaxira
nusxa yaratadi.
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from apps.butchering.models import (
    Butchering, ButcheringExpense, ButcheringOutput,
    ButcheringSpecification, ButcheringSpecificationItem,
)
from apps.customers.models import Customer
from apps.expenses.models import Expense, ExpenseCategory
from apps.inventory.models import InventoryCount, InventoryCountItem, StockMovement
from apps.kassa.models import CashTransaction
from apps.payments.models import Payment
from apps.products.models import Product, ProductCategory
from apps.purchases.models import Purchase, PurchaseExpense, PurchaseItem
from apps.sales.models import Sale, SaleItem
from apps.suppliers.models import Supplier

# Tartib muhim — PROTECT/CASCADE cheklovlariga mos, avval "farzand"
# yozuvlar, keyin ular ishora qilgan "ota" yozuvlar o'chiriladi.
MODELS_IN_DELETE_ORDER = [
    Payment,
    CashTransaction,
    StockMovement,
    InventoryCountItem,
    InventoryCount,
    SaleItem,
    Sale,
    ButcheringExpense,
    ButcheringOutput,
    Butchering,
    ButcheringSpecificationItem,
    ButcheringSpecification,
    PurchaseExpense,
    PurchaseItem,
    Purchase,
    Expense,
    ExpenseCategory,
    Product,
    ProductCategory,
    Customer,
    Supplier,
]


class Command(BaseCommand):
    help = "Barcha biznes ma'lumotlarini o'chirib, bazani nol holatga qaytaradi (foydalanuvchi hisoblari saqlanadi)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', action='store_true',
            help="Haqiqatan o'chirishni tasdiqlash. Bo'lmasa, faqat nechta yozuv borligini ko'rsatib, hech narsa o'chmaydi.",
        )
        parser.add_argument(
            '--no-backup', action='store_true',
            help="db.sqlite3 zaxira nusxasini yaratmasdan o'tkazib yuborish (tavsiya etilmaydi).",
        )

    def handle(self, *args, **options):
        counts = {model.__name__: model.objects.count() for model in MODELS_IN_DELETE_ORDER}
        total = sum(counts.values())

        self.stdout.write("O'chiriladigan yozuvlar:")
        for name, n in counts.items():
            if n:
                self.stdout.write(f"  {name}: {n}")
        self.stdout.write(f"Jami: {total} ta yozuv.\n")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Baza allaqachon bo'sh."))
            return

        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                "Hech narsa o'chirilmadi (dry-run). Haqiqatan o'chirish uchun:\n"
                "  python manage.py reset_business_data --yes"
            ))
            return

        if not options['no_backup']:
            self._backup_sqlite_if_applicable()

        with transaction.atomic():
            for model in MODELS_IN_DELETE_ORDER:
                model.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(
            f"\n{total} ta yozuv o'chirildi. Baza nol holatda. Foydalanuvchi hisoblari saqlanib qoldi."
        ))

    def _backup_sqlite_if_applicable(self):
        if connection.vendor != 'sqlite':
            return
        db_path = Path(settings.DATABASES['default']['NAME'])
        if not db_path.exists():
            return
        stamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        backup_path = db_path.with_name(f'{db_path.name}.bak-{stamp}')
        shutil.copy2(db_path, backup_path)
        self.stdout.write(f"Zaxira nusxa yaratildi: {backup_path}")
