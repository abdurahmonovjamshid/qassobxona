from django.db import migrations


def seed(apps, schema_editor):
    Warehouse = apps.get_model('inventory', 'Warehouse')
    StockMovement = apps.get_model('inventory', 'StockMovement')
    main, _ = Warehouse.objects.get_or_create(name='Asosiy sklad', defaults={'is_default': True})
    Warehouse.objects.get_or_create(name='2-sklad')
    # Mavjud barcha harakatlar asosiy omborda bo'lgan deb hisoblanadi.
    StockMovement.objects.filter(warehouse__isnull=True).update(warehouse=main)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_warehouse_stocktransfer'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
