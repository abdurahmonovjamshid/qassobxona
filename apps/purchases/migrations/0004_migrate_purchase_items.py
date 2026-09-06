from decimal import Decimal

from django.db import migrations


def migrate_items(apps, schema_editor):
    Purchase = apps.get_model('purchases', 'Purchase')
    PurchaseItem = apps.get_model('purchases', 'PurchaseItem')

    for purchase in Purchase.objects.filter(product__isnull=False):
        total = (purchase.net_weight * purchase.price_per_kg).quantize(Decimal('0.01'))
        PurchaseItem.objects.create(
            purchase=purchase,
            product_id=purchase.product_id,
            animal_type=purchase.animal_type or '',
            gross_weight=purchase.gross_weight,
            net_weight=purchase.net_weight,
            pieces=0,
            price_per_kg=purchase.price_per_kg,
            total=total,
            landed_unit_cost=purchase.price_per_kg,
        )


def reverse_items(apps, schema_editor):
    Purchase = apps.get_model('purchases', 'Purchase')
    PurchaseItem = apps.get_model('purchases', 'PurchaseItem')

    for item in PurchaseItem.objects.select_related('purchase').all():
        purchase = item.purchase
        Purchase.objects.filter(pk=purchase.pk).update(
            product_id=item.product_id,
            animal_type=item.animal_type,
            gross_weight=item.gross_weight,
            net_weight=item.net_weight,
            price_per_kg=item.price_per_kg,
        )
    PurchaseItem.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0003_purchaseitem'),
    ]

    operations = [
        migrations.RunPython(migrate_items, reverse_items),
    ]
