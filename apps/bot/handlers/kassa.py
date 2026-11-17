"""Kassa (faqat o'qish uchun): joriy balans va so'nggi harakatlar.
Qo'lda balans tuzatish (`kassa_add_balance`, superuser-only veb-sayt
funksiyasi) ataylab botga qo'shilmagan — TZ.txt/reja bo'yicha kelishilgan
chegara: bu amal veb-saytda yoki Django admin orqali bajariladi."""
from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import date_fmt, som
from apps.bot.handlers.common import register_menu
from apps.kassa.models import CashTransaction
from apps.kassa.services import cash_service


@register_menu(keyboards.MENU_KASSA)
def kassa_menu(message, tg_user):
    lines = ['Kassa balanslari:']
    lines += [f"{b['register'].name}: {som(b['balance'])}" for b in cash_service.get_balances()]
    lines += ['', "So'nggi harakatlar:"]
    moves = cash_service.attach_document_info(CashTransaction.objects.select_related('register')[:10])
    for m in moves:
        sign = '+' if m.amount >= 0 else ''
        extra = ' — '.join(filter(None, [m.party, m.doc_notes]))
        lines.append(
            f'{date_fmt(m.date)} [{m.register.name}] {m.get_transaction_type_display()}: {sign}{som(m.amount)}'
            + (f' ({extra})' if extra else '')
        )
    bot.send_message(message.chat.id, '\n'.join(lines))
