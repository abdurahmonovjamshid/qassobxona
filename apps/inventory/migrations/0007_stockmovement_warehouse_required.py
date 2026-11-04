import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_seed_warehouses'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='warehouse',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movements', to='inventory.warehouse'),
        ),
    ]
