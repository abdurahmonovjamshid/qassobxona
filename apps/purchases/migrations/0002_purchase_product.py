import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        ('purchases', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchase',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="Ombor kirimi qilinadigan mahsulot (masalan: 'Mol (butun)'). Tasdiqlash uchun shart.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name='purchases',
                to='products.product',
            ),
        ),
    ]
