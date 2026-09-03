"""Mahsulot kategoriyalarini boyitish:

- Avvalgi umumiy 'MEAT' kategoriyasidagi (mol go'shti kesimlari) mahsulotlar
  yangi 'BEEF' kategoriyasiga o'tkaziladi.
- Tovuq go'shti va qo'y go'shti bo'yicha real bozor narxlariga yaqin
  namunaviy mahsulotlar va ularning boshlang'ich ombor qoldig'i qo'shiladi
  — savdo katalogidagi kategoriya bo'yicha filtr mazmunli bo'lishi uchun.
"""
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


CHICKEN_PRODUCTS = [
    # (nomi, kod, sotuv narxi, tannarx, boshlang'ich qoldiq kg)
    ('Tovuq (butun)', 'TOVUQ-BUTUN', Decimal('32000'), Decimal('24000'), Decimal('40')),
    ("Tovuq ko'kragi", 'TOVUQ-KOKRAK', Decimal('42000'), Decimal('31000'), Decimal('25')),
    ('Tovuq buti', 'TOVUQ-BUT', Decimal('36000'), Decimal('27000'), Decimal('30')),
    ('Tovuq qanoti', 'TOVUQ-QANOT', Decimal('38000'), Decimal('28000'), Decimal('15')),
]

LAMB_PRODUCTS = [
    ("Qo'y go'shti (lahm)", 'QOY-LAHM', Decimal('130000'), Decimal('100000'), Decimal('20')),
    ("Qo'y qovurg'asi", 'QOY-QOVURGA', Decimal('125000'), Decimal('96000'), Decimal('15')),
    ("Qo'y boldiri", 'QOY-BOLDIR', Decimal('100000'), Decimal('78000'), Decimal('12')),
    ("Qo'y kuyruq yog'i", 'QOY-YOG', Decimal('75000'), Decimal('58000'), Decimal('8')),
]


def seed_categories(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    StockMovement = apps.get_model('inventory', 'StockMovement')
    today = timezone.localdate()

    Product.objects.filter(category='MEAT').update(category='BEEF')

    for name, code, sale_price, cost, qty in CHICKEN_PRODUCTS + LAMB_PRODUCTS:
        if Product.objects.filter(code=code).exists():
            continue
        category = 'CHICKEN' if code.startswith('TOVUQ') else 'LAMB'
        product = Product.objects.create(
            name=name, code=code, category=category, unit='kg',
            sale_price=sale_price, active=True,
        )
        StockMovement.objects.create(
            product=product, quantity=qty, movement_type='ADJUSTMENT',
            direction='IN', unit_cost=cost,
            reference='SEED:initial-stock', date=today,
        )


def unseed_categories(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    codes = [p[1] for p in CHICKEN_PRODUCTS + LAMB_PRODUCTS]
    Product.objects.filter(code__in=codes).delete()
    Product.objects.filter(category='BEEF').update(category='MEAT')


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_alter_product_category'),
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
