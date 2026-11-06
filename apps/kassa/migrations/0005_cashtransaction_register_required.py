import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kassa', '0004_seed_cash_registers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cashtransaction',
            name='register',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='kassa.cashregister', verbose_name='Kassa'),
        ),
    ]
