"""Hisobotlar (faqat o'qish uchun): `apps/reports/services/report_service.py`
funksiyalarini chaqirib, natijani matn ko'rinishida yuboradi. Sana filtri
ro'yxat sahifalaridagi standart bilan bir xil — berilmasa joriy oy boshidan
bugungacha (`apps/common/date_filters.py::get_date_range`)."""
from django.utils import timezone

from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import kg, som
from apps.bot.handlers.common import register_menu
from apps.bot.state import register_callback
from apps.reports.services import report_service


def _current_month_range():
    today = timezone.localdate()
    return today.replace(day=1), today


@register_menu(keyboards.MENU_REPORTS)
def reports_menu(message, tg_user):
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('💰 Savdo', callback_data='rep:sales'))
    kb.row(types.InlineKeyboardButton('🛒 Xarid', callback_data='rep:purchases'))
    kb.row(types.InlineKeyboardButton('📦 Ombor', callback_data='rep:inventory'))
    kb.row(types.InlineKeyboardButton('👥 Debitor', callback_data='rep:debtor'))
    kb.row(types.InlineKeyboardButton('🚚 Kreditor', callback_data='rep:creditor'))
    kb.row(types.InlineKeyboardButton('📈 Foyda', callback_data='rep:profit'))
    bot.send_message(
        message.chat.id, "Hisobotlar bo'limi (joriy oy uchun, boshqa davr veb-saytda):",
        reply_markup=kb,
    )


@register_callback('rep')
def show_report(call, tg_user):
    kind = call.data.split(':', 1)[1]
    bot.answer_callback_query(call.id)
    handler = {
        'sales': _sales, 'purchases': _purchases, 'inventory': _inventory,
        'debtor': _debtor, 'creditor': _creditor, 'profit': _profit,
    }[kind]
    handler(call.message.chat.id)


def _sales(chat_id):
    date_from, date_to = _current_month_range()
    r = report_service.sales_report(date_from=date_from, date_to=date_to)
    lines = [
        f'💰 Savdo hisoboti ({date_from} — {date_to})', '',
        f"Sotuvlar soni: {r['sales'].count()}",
        f"Jami: {som(r['total_amount'])}",
        f"To'langan: {som(r['total_paid'])}",
        f"Qarz: {som(r['total_debt'])}",
    ]
    bot.send_message(chat_id, '\n'.join(lines))


def _purchases(chat_id):
    date_from, date_to = _current_month_range()
    r = report_service.purchase_report(date_from=date_from, date_to=date_to)
    lines = [
        f'🛒 Xarid hisoboti ({date_from} — {date_to})', '',
        f"Xaridlar soni: {r['purchases'].count()}",
        f"Jami vazn: {kg(r['total_weight'])}",
        f"Jami: {som(r['total_amount'])}",
        f"To'langan: {som(r['total_paid'])}",
        f"Qarz: {som(r['total_debt'])}",
    ]
    bot.send_message(chat_id, '\n'.join(lines))


def _inventory(chat_id):
    rows = report_service.inventory_report()
    lines = ['📦 Ombor hisoboti:', '']
    for row in rows:
        if row['stock'] <= 0 and row['total_in'] == 0:
            continue
        lines.append(
            f"{row['product'].name}: kirim {kg(row['total_in'])}, chiqim {kg(row['total_out'])}, "
            f"qoldiq {kg(row['stock'])}, o'rt. tannarx {som(row['avg_cost'])}/kg"
        )
    bot.send_message(chat_id, '\n'.join(lines))


def _debtor(chat_id):
    rows = report_service.debtor_report()
    lines = ['👥 Debitor hisoboti:', '']
    for r in rows[:50]:
        lines.append(f"{r['customer'].name}: {som(r['debt'])}")
    if not rows:
        lines.append('Qarzdorlar yo\'q.')
    bot.send_message(chat_id, '\n'.join(lines))


def _creditor(chat_id):
    rows = report_service.creditor_report()
    lines = ['🚚 Kreditor hisoboti:', '']
    for r in rows[:50]:
        lines.append(f"{r['supplier'].name}: {som(r['debt'])}")
    if not rows:
        lines.append('Qarzimiz yo\'q.')
    bot.send_message(chat_id, '\n'.join(lines))


def _profit(chat_id):
    date_from, date_to = _current_month_range()
    r = report_service.profit_report(date_from=date_from, date_to=date_to)
    lines = [
        f'📈 Foyda hisoboti ({date_from} — {date_to})', '',
        f"Savdo (revenue): {som(r['revenue'])}",
        f"Tannarx (cost): {som(r['cost'])}",
        f"Yalpi foyda: {som(r['gross_profit'])}",
        f"Xarajatlar: {som(r['expenses_total'])}",
        f"Sof foyda: {som(r['net_profit'])}",
    ]
    bot.send_message(chat_id, '\n'.join(lines))
