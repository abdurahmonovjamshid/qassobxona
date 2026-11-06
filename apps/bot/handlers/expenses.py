"""Xarajat (Expense) oqimi: kategoriya -> summa -> to'lov turi -> sana ->
izoh -> tasdiqlash. `apps/expenses/views.py::expense_create` bilan bir xil:
`expense_services.create_expense()` orqali Expense saqlanadi va tanlangan
kassadan chiqim qilinadi (kassada mablag' yetarli bo'lmasa xatolik chiqadi)."""
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.bot import choices, keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import date_fmt, errors_to_text, som
from apps.bot.handlers.common import register_menu
from apps.bot.inputs import is_skip, parse_decimal
from apps.bot.pickers import register_calendar, register_pagination, send_calendar, send_picker
from apps.bot.state import register_callback, register_state, set_state
from apps.expenses import services as expense_services
from apps.expenses.models import Expense, ExpenseCategory
from apps.kassa.models import CashRegister
from apps.kassa.services import cash_service

register_pagination('exp_cat', choices.active_expense_categories)
register_pagination('exp_ptype', choices.cash_registers)


@register_menu(keyboards.MENU_EXPENSES)
def expenses_menu(message, tg_user):
    balances = '\n'.join(f"{b['register'].name}: {som(b['balance'])}" for b in cash_service.get_balances())
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('➕ Yangi xarajat', callback_data='exnew:1'))
    kb.row(types.InlineKeyboardButton("📋 So'nggi xarajatlar", callback_data='exlist:0'))
    bot.send_message(message.chat.id, f'Xarajatlar bo\'limi.\n{balances}', reply_markup=kb)


@register_callback('exnew')
def start_expense(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'expense.picking_category')
    send_picker(call.message.chat.id, 'exp_cat', choices.active_expense_categories(), 'Xarajat kategoriyasi:')


@register_callback('exp_cat')
def pick_category(call, tg_user):
    category_id = int(call.data.split(':', 1)[1])
    from apps.expenses.models import ExpenseCategory
    category = ExpenseCategory.objects.get(pk=category_id)
    bot.answer_callback_query(call.id, category.name)
    set_state(tg_user, 'expense.amount', category_id=category_id, category_name=category.name)
    bot.send_message(call.message.chat.id, f'{category.name} — summasi?', reply_markup=keyboards.cancel_only())


@register_state('expense.amount')
def on_amount(message, tg_user):
    amount = parse_decimal(message.text)
    if amount is None or amount <= 0:
        bot.send_message(message.chat.id, 'Xarajat musbat bolishi kerak. Qayta kiriting:')
        return
    set_state(tg_user, 'expense.picking_type', amount=str(amount))
    send_picker(message.chat.id, 'exp_ptype', choices.cash_registers(), "Qaysi kassa?")


@register_callback('exp_ptype')
def pick_payment_type(call, tg_user):
    code = call.data.split(':', 1)[1]
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'expense.date', payment_type=code)
    send_calendar(call.message.chat.id, 'exp_date', 'Sana?')


def _on_date_picked(call, tg_user, picked):
    set_state(tg_user, 'expense.description', date=picked.isoformat())
    bot.send_message(call.message.chat.id, 'Izoh? (ixtiyoriy)', reply_markup=keyboards.cancel_and_skip())


register_calendar('exp_date', _on_date_picked)


@register_state('expense.description')
def on_description(message, tg_user):
    description = '' if is_skip(message.text) else message.text.strip()
    set_state(tg_user, 'expense.confirm', description=description)
    data = tg_user.data
    lines = [
        f"Kategoriya: {data['category_name']}",
        f"Summa: {som(data['amount'])}",
        f"Kassa: {dict(choices.cash_registers()).get(data['payment_type'], data['payment_type'])}",
        f"Sana: {date_fmt(data['date'])}",
    ]
    if description:
        lines.append(f'Izoh: {description}')
    lines.append('')
    lines.append('Tasdiqlaysizmi?')
    bot.send_message(message.chat.id, '\n'.join(lines), reply_markup=keyboards.confirm_cancel_inline('exconfirm:1'))


@register_callback('exconfirm')
def confirm_expense(call, tg_user):
    bot.answer_callback_query(call.id, 'Yuborildi...')
    data = tg_user.data
    user = tg_user.django_user
    try:
        expense = expense_services.create_expense(
            category=ExpenseCategory.objects.get(pk=data['category_id']), amount=Decimal(data['amount']),
            date=data['date'], description=data.get('description', ''),
            cash_register=CashRegister.for_payment_type(data.get('payment_type')), user=user,
        )
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id, f"✅ Xarajat qo'shildi: {som(expense.amount)}",
            reply_markup=keyboards.main_menu(),
        )
    except ValidationError as exc:
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id, f"❌ Xatolik:\n{errors_to_text(exc)}",
            reply_markup=keyboards.main_menu(),
        )


@register_callback('exlist')
def list_expenses(call, tg_user):
    bot.answer_callback_query(call.id)
    expenses = Expense.objects.select_related('category').all()[:10]
    if not expenses:
        bot.send_message(call.message.chat.id, "Hozircha xarajatlar yo'q.")
        return
    lines = ["🧾 So'nggi xarajatlar:", '']
    for e in expenses:
        lines.append(f'{date_fmt(e.date)} | {e.category.name}: {som(e.amount)} ({e.get_payment_type_display()})')
    bot.send_message(call.message.chat.id, '\n'.join(lines))
