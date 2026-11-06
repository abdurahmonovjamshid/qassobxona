from django.db import migrations


def seed(apps, schema_editor):
    CashRegister = apps.get_model('kassa', 'CashRegister')
    CashTransaction = apps.get_model('kassa', 'CashTransaction')
    Payment = apps.get_model('payments', 'Payment')
    Expense = apps.get_model('expenses', 'Expense')

    cash, _ = CashRegister.objects.get_or_create(code='CASH', defaults={'name': 'Naqd kassa', 'is_default': True})
    CashRegister.objects.get_or_create(code='CARD', defaults={'name': 'Karta kassa'})
    # Shu paytgacha kassada yozilgan barcha harakatlar naqd kassada bo'lgan.
    CashTransaction.objects.filter(register__isnull=True).update(register=cash)
    # Eski naqd to'lov/xarajatlar kassaga yozilgan edi — ular Naqd kassaga
    # bog'lanadi. Karta/o'tkazma bilan qilingan eski to'lovlar kassaga
    # yozilmagan edi, shuning uchun ularning kassasi bo'sh qoladi.
    Payment.objects.filter(payment_type='CASH', cash_register__isnull=True).update(cash_register=cash)
    Expense.objects.filter(payment_type='CASH', cash_register__isnull=True).update(cash_register=cash)


class Migration(migrations.Migration):

    dependencies = [
        ('kassa', '0003_cashregister'),
        ('payments', '0003_payment_cash_register_alter_payment_payment_type'),
        ('expenses', '0002_expense_cash_register_alter_expense_payment_type'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
