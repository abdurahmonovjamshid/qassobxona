"""Mijozlar: ro'yxat/qarzdorlar/qidirish (o'qish uchun) va yangi mijoz
qo'shish. Tarix (`history`) hisoblash mantig'i `apps/customers/views.py::customer_detail`
bilan bir xil (boshlang'ich saldo + sotuvlar + to'lovlar, sana bo'yicha
saralangan)."""
from decimal import Decimal

from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import som
from apps.bot.handlers.common import register_menu
from apps.bot.inputs import is_skip, parse_decimal
from apps.bot.pickers import send_picker
from apps.bot.state import register_callback, register_state, set_state
from apps.customers.models import Customer


@register_menu(keyboards.MENU_CUSTOMERS)
def customers_menu(message, tg_user):
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('📋 Barcha mijozlar', callback_data='custlist:1'))
    kb.row(types.InlineKeyboardButton('💰 Qarzdorlar', callback_data='custdebt:1'))
    kb.row(types.InlineKeyboardButton('🔍 Qidirish', callback_data='custsearch:1'))
    kb.row(types.InlineKeyboardButton('➕ Yangi mijoz', callback_data='custnew:1'))
    bot.send_message(message.chat.id, 'Mijozlar bo\'limi:', reply_markup=kb)


@register_callback('custlist')
def list_customers(call, tg_user):
    bot.answer_callback_query(call.id)
    customers = Customer.objects.filter(active=True).order_by('name')[:50]
    if not customers:
        bot.send_message(call.message.chat.id, "Mijozlar yo'q.")
        return
    lines = ['👥 Mijozlar:', '']
    for c in customers:
        lines.append(f'{c.name} — qarz: {som(c.get_total_debt())}')
    bot.send_message(call.message.chat.id, '\n'.join(lines))


@register_callback('custdebt')
def debtors(call, tg_user):
    bot.answer_callback_query(call.id)
    from apps.reports.services import report_service
    rows = report_service.debtor_report()
    if not rows:
        bot.send_message(call.message.chat.id, "Qarzdor mijozlar yo'q.")
        return
    lines = ['💰 Qarzdorlar:', '']
    for r in rows[:50]:
        lines.append(f"{r['customer'].name}: {som(r['debt'])}")
    bot.send_message(call.message.chat.id, '\n'.join(lines))


@register_callback('custsearch')
def start_search(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'customer.search')
    bot.send_message(call.message.chat.id, 'Mijoz ismini (yoki bir qismini) kiriting:', reply_markup=keyboards.cancel_only())


@register_state('customer.search')
def on_search(message, tg_user):
    q = message.text.strip()
    matches = list(Customer.objects.filter(name__icontains=q)[:10])
    tg_user.reset_state()
    if not matches:
        bot.send_message(message.chat.id, "Hech narsa topilmadi.", reply_markup=keyboards.main_menu())
        return
    if len(matches) == 1:
        _send_detail(message.chat.id, matches[0])
        return
    send_picker(message.chat.id, 'cust_pick', [(c.id, c.name) for c in matches], 'Topilganlar:')


@register_callback('cust_pick')
def pick_search_result(call, tg_user):
    customer_id = int(call.data.split(':', 1)[1])
    bot.answer_callback_query(call.id)
    _send_detail(call.message.chat.id, Customer.objects.get(pk=customer_id))


def _send_detail(chat_id, customer):
    from apps.sales.models import Sale
    sales = customer.sales.exclude(status=Sale.Status.CANCELLED)
    payments = customer.payments.all()

    history = []
    if customer.opening_balance:
        history.append((customer.created_at.date(), "Boshlang'ich qarz", customer.opening_balance))
    for sale in sales:
        history.append((sale.date, f'Sotuv {sale.sale_number}', sale.total_amount))
    for payment in payments:
        history.append((payment.date, "To'lov", -payment.amount))
    history.sort(key=lambda h: h[0])

    lines = [
        f'👤 {customer.name}',
        customer.phone or '',
        '',
        f'Jami xarid: {som(customer.get_total_sales())}',
        f"Jami to'lov: {som(customer.get_total_payments())}",
        f'Qarz: {som(customer.get_total_debt())}',
        '',
        'Oxirgi harakatlar:',
    ]
    for d, op, amount in history[-10:]:
        sign = '+' if amount >= 0 else ''
        lines.append(f'{d} {op} {sign}{som(amount)}')
    bot.send_message(chat_id, '\n'.join(l for l in lines if l is not None))


@register_callback('custnew')
def start_create(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'customer.name')
    bot.send_message(call.message.chat.id, "Yangi mijoz ismi?", reply_markup=keyboards.cancel_only())


@register_state('customer.name')
def on_name(message, tg_user):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, 'Ism bolishi kerak. Qayta kiriting:')
        return
    set_state(tg_user, 'customer.phone', name=name)
    bot.send_message(message.chat.id, 'Telefon raqami? (ixtiyoriy)', reply_markup=keyboards.cancel_and_skip())


@register_state('customer.phone')
def on_phone(message, tg_user):
    phone = '' if is_skip(message.text) else message.text.strip()
    set_state(tg_user, 'customer.address', phone=phone)
    bot.send_message(message.chat.id, 'Manzil? (ixtiyoriy)', reply_markup=keyboards.cancel_and_skip())


@register_state('customer.address')
def on_address(message, tg_user):
    address = '' if is_skip(message.text) else message.text.strip()
    set_state(tg_user, 'customer.opening_balance', address=address)
    bot.send_message(
        message.chat.id, "Boshlang'ich qarz? (ixtiyoriy, musbat = mijoz qarzdor)",
        reply_markup=keyboards.cancel_and_skip(),
    )


@register_state('customer.opening_balance')
def on_opening_balance(message, tg_user):
    if is_skip(message.text):
        opening = Decimal('0')
    else:
        opening = parse_decimal(message.text)
        if opening is None:
            bot.send_message(message.chat.id, "Son kiriting yoki o'tkazib yuboring:")
            return
    data = dict(tg_user.data)
    customer = Customer.objects.create(
        name=data['name'], phone=data.get('phone', ''), address=data.get('address', ''),
        opening_balance=opening, active=True,
    )
    tg_user.reset_state()
    bot.send_message(message.chat.id, f"✅ {customer.name} qo'shildi.", reply_markup=keyboards.main_menu())
