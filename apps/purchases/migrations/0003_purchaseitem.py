import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        ('purchases', '0002_purchase_product'),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchaseItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('animal_type', models.CharField(blank=True, max_length=80)),
                ('gross_weight', models.DecimalField(decimal_places=3, max_digits=10)),
                ('net_weight', models.DecimalField(decimal_places=3, max_digits=10)),
                ('pieces', models.PositiveIntegerField(default=0, help_text="Dona/bo'lak soni")),
                ('price_per_kg', models.DecimalField(decimal_places=2, max_digits=14)),
                ('total', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('landed_unit_cost', models.DecimalField(
                    decimal_places=2, default=0, max_digits=14,
                    help_text="Qo'shimcha xarajatlar qo'shilgan yakuniy tannarx/kg",
                )),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='purchase_items', to='products.product')),
                ('purchase', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='purchases.purchase')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
