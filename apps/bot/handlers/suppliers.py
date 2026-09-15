"""Yetkazib beruvchilar: ro'yxat/qarzdorlar/qidirish (o'qish uchun) va yangi
yetkazib beruvchi qo'shish. `apps/suppliers/views.py::supplier_detail` bilan
bir xil tarix mantig'i (boshlang'ich saldo + xaridlar + to'lovlar)."""
from decimal import Decimal

from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import som
from apps.bot.handlers.common import register_menu
from apps.bot.inputs import is_skip, parse_decimal
from apps.bot.pickers import send_picker
from apps.bot.state import register_callback, register_state, set_state
from apps.suppliers.models import Supplier


@register_menu(keyboards.MENU_SUPPLIERS)
def suppliers_menu(message, tg_user):
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('📋 Barcha yetkazib beruvchilar', callback_data='suplist:1'))
    kb.row(types.InlineKeyboardButton('💰 Qarzdorliklarimiz', callback_data='supdebt:1'))
    kb.row(types.InlineKeyboardButton('🔍 Qidirish', callback_data='supsearch:1'))
    kb.row(types.InlineKeyboardButton('➕ Yangi yetkazib beruvchi', callback_data='supnew:1'))
    bot.send_message(message.chat.id, 'Yetkazib beruvchilar bo\'limi:', reply_markup=kb)


@register_callback('suplist')
def list_suppliers(call, tg_user):
    bot.answer_callback_query(call.id)
    suppliers = Supplier.objects.filter(active=True).order_by('name')[:50]
    if not suppliers:
        bot.send_message(call.message.chat.id, "Yetkazib beruvchilar yo'q.")
        return
    lines = ['🚚 Yetkazib beruvchilar:', '']
    for s in suppliers:
        lines.append(f'{s.name} — qarzimiz: {som(s.get_total_debt())}')
    bot.send_message(call.message.chat.id, '\n'.join(lines))


@register_callback('supdebt')
def creditors(call, tg_user):
    bot.answer_callback_query(call.id)
    from apps.reports.services import report_service
    rows = report_service.creditor_report()
    if not rows:
        bot.send_message(call.message.chat.id, "Qarzimiz bor yetkazib beruvchilar yo'q.")
        return
    lines = ['💰 Kreditor qarzdorlik:', '']
    for r in rows[:50]:
        lines.append(f"{r['supplier'].name}: {som(r['debt'])}")
    bot.send_message(call.message.chat.id, '\n'.join(lines))


@register_callback('supsearch')
def start_search(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'supplier.search')
    bot.send_message(call.message.chat.id, 'Yetkazib beruvchi nomini (yoki bir qismini) kiriting:', reply_markup=keyboards.cancel_only())


@register_state('supplier.search')
def on_search(message, tg_user):
    q = message.text.strip()
    matches = list(Supplier.objects.filter(name__icontains=q)[:10])
    tg_user.reset_state()
    if not matches:
        bot.send_message(message.chat.id, "Hech narsa topilmadi.", reply_markup=keyboards.main_menu())
        return
    if len(matches) == 1:
        _send_detail(message.chat.id, matches[0])
        return
    send_picker(message.chat.id, 'sup_pick', [(s.id, s.name) for s in matches], 'Topilganlar:')


@register_callback('sup_pick')
def pick_search_result(call, tg_user):
    supplier_id = int(call.data.split(':', 1)[1])
    bot.answer_callback_query(call.id)
    _send_detail(call.message.chat.id, Supplier.objects.get(pk=supplier_id))


def _send_detail(chat_id, supplier):
    from apps.purchases.models import Purchase
    purchases = supplier.purchases.exclude(status=Purchase.Status.CANCELLED)
    payments = supplier.payments.all()

    history = []
    if supplier.opening_balance:
        history.append((supplier.created_at.date(), "Boshlang'ich qarz", supplier.opening_balance))
    for purchase in purchases:
        history.append((purchase.date, f'Xarid {purchase.purchase_number}', purchase.total_amount))
    for payment in payments:
        history.append((payment.date, "To'lov", -payment.amount))
    history.sort(key=lambda h: h[0])

    lines = [
        f'🚚 {supplier.name}',
        supplier.phone or '',
        '',
        f'Jami xarid: {som(supplier.get_total_purchases())}',
        f"Jami to'lov: {som(supplier.get_total_payments())}",
        f'Qarzimiz: {som(supplier.get_total_debt())}',
        '',
        'Oxirgi harakatlar:',
    ]
    for d, op, amount in history[-10:]:
        sign = '+' if amount >= 0 else ''
        lines.append(f'{d} {op} {sign}{som(amount)}')
    bot.send_message(chat_id, '\n'.join(l for l in lines if l is not None))


@register_callback('supnew')
def start_create(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'supplier.name')
    bot.send_message(call.message.chat.id, "Yangi yetkazib beruvchi nomi?", reply_markup=keyboards.cancel_only())


@register_state('supplier.name')
def on_name(message, tg_user):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, 'Nom bolishi kerak. Qayta kiriting:')
        return
    set_state(tg_user, 'supplier.phone', name=name)
    bot.send_message(message.chat.id, 'Telefon raqami? (ixtiyoriy)', reply_markup=keyboards.cancel_and_skip())


@register_state('supplier.phone')
def on_phone(message, tg_user):
    phone = '' if is_skip(message.text) else message.text.strip()
    set_state(tg_user, 'supplier.address', phone=phone)
    bot.send_message(message.chat.id, 'Manzil? (ixtiyoriy)', reply_markup=keyboards.cancel_and_skip())


@register_state('supplier.address')
def on_address(message, tg_user):
    address = '' if is_skip(message.text) else message.text.strip()
    set_state(tg_user, 'supplier.opening_balance', address=address)
    bot.send_message(
        message.chat.id, "Boshlang'ich qarzimiz? (ixtiyoriy, musbat = bizning qarzimiz)",
        reply_markup=keyboards.cancel_and_skip(),
    )


@register_state('supplier.opening_balance')
def on_opening_balance(message, tg_user):
    if is_skip(message.text):
        opening = Decimal('0')
    else:
        opening = parse_decimal(message.text)
        if opening is None:
            bot.send_message(message.chat.id, "Son kiriting yoki o'tkazib yuboring:")
            return
    data = dict(tg_user.data)
    supplier = Supplier.objects.create(
        name=data['name'], phone=data.get('phone', ''), address=data.get('address', ''),
        opening_balance=opening, active=True,
    )
    tg_user.reset_state()
    bot.send_message(message.chat.id, f"✅ {supplier.name} qo'shildi.", reply_markup=keyboards.main_menu())
