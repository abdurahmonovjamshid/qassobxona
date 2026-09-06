from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0004_migrate_purchase_items'),
    ]

    operations = [
        migrations.RemoveField(model_name='purchase', name='product'),
        migrations.RemoveField(model_name='purchase', name='animal_type'),
        migrations.RemoveField(model_name='purchase', name='gross_weight'),
        migrations.RemoveField(model_name='purchase', name='net_weight'),
        migrations.RemoveField(model_name='purchase', name='price_per_kg'),
    ]
