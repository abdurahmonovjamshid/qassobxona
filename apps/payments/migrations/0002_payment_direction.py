from django.db import migrations, models


def set_direction_from_partner(apps, schema_editor):
    """Eski yozuvlarda yo'nalish maydoni yo'q edi va u `customer`/`supplier`dan
    taxmin qilinardi: mijozdan pul olinardi (kirim), yetkazib beruvchiga
    to'lanardi (chiqim). Mavjud ma'lumotlar o'zgarmasligi uchun aynan shu
    taxmin yozib qo'yiladi."""
    Payment = apps.get_model('payments', 'Payment')
    Payment.objects.filter(supplier__isnull=False).update(direction='OUT')
    Payment.objects.filter(supplier__isnull=True).update(direction='IN')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='direction',
            field=models.CharField(
                choices=[('IN', 'Kirim (pul bizga keldi)'), ('OUT', 'Chiqim (pul bizdan ketdi)')],
                default='IN', max_length=3,
            ),
        ),
        migrations.RunPython(set_direction_from_partner, noop),
    ]
