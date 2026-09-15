"""Kassa (faqat o'qish uchun): joriy balans va so'nggi harakatlar.
Qo'lda balans tuzatish (`kassa_add_balance`, superuser-only veb-sayt
funksiyasi) ataylab botga qo'shilmagan — TZ.txt/reja bo'yicha kelishilgan
chegara: bu amal veb-saytda yoki Django admin orqali bajariladi."""
from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import som
from apps.bot.handlers.common import register_menu
from apps.kassa.models import CashTransaction
from apps.kassa.services import cash_service


@register_menu(keyboards.MENU_KASSA)
def kassa_menu(message, tg_user):
    balance = cash_service.get_balance()
    moves = CashTransaction.objects.all()[:10]
    lines = [f'💵 Kassa balansi: {som(balance)}', '', "So'nggi harakatlar:"]
    for m in moves:
        sign = '+' if m.amount >= 0 else ''
        lines.append(f'{m.date} {m.get_transaction_type_display()}: {sign}{som(m.amount)}')
    bot.send_message(message.chat.id, '\n'.join(lines))
