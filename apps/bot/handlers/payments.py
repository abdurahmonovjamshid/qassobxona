"""To'lov (Payment) oqimi: mijoz yoki yetkazib beruvchi -> (ixtiyoriy) qarzli
sotuv/xaridga bog'lash -> summa -> to'lov turi -> sana -> izoh -> tasdiqlash.

`apps/payments/services/payment_service.py::create_payment()` chaqiriladi —
tegishli Sale/Purchase qarzini qayta hisoblash va (naqd bo'lsa) kassa
effektini qo'llash shu servis ichida, o'zgarishsiz. "Bekor qilish" esa
website'dagi kabi `delete_payment()` — Payment qatori HAQIQATDA o'chiriladi
(faqat kassa effekti reversing yozuv bilan tuzatiladi), boshqa hujjatlardagi
kabi soft-cancel EMAS."""
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.bot import choices, keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import errors_to_text, som
from apps.bot.handlers.common import register_menu
from apps.bot.inputs import is_skip, parse_date, parse_decimal
from apps.bot.pickers import register_pagination, send_picker
from apps.bot.state import register_callback, register_state, set_state
from apps.payments.models import Payment
from apps.payments.services import payment_service

register_pagination('pay_cust', choices.active_customers)
register_pagination('pay_sup', choices.active_suppliers)
register_pagination('pay_ptype', lambda: choices.PAYMENT_TYPES)


@register_menu(keyboards.MENU_PAYMENTS)
def payments_menu(message, tg_user):
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('👥 Mijozdan to\'lov', callback_data='paynew:customer'))
    kb.row(types.InlineKeyboardButton('🚚 Yetkazib beruvchiga to\'lov', callback_data='paynew:supplier'))
    kb.row(types.InlineKeyboardButton("📋 So'nggi to'lovlar", callback_data='paylist:0'))
    bot.send_message(message.chat.id, "To'lov bo'limi:", reply_markup=kb)


@register_callback('paynew')
def start_payment(call, tg_user):
    party_type = call.data.split(':', 1)[1]
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'pay.picking_party', party_type=party_type)
    if party_type == 'customer':
        send_picker(call.message.chat.id, 'pay_cust', choices.active_customers(), 'Mijozni tanlang:')
    else:
        send_picker(call.message.chat.id, 'pay_sup', choices.active_suppliers(), 'Yetkazib beruvchini tanlang:')


@register_callback('pay_cust')
def pick_party_customer(call, tg_user):
    customer_id = int(call.data.split(':', 1)[1])
    from apps.customers.models import Customer
    customer = Customer.objects.get(pk=customer_id)
    bot.answer_callback_query(call.id, customer.name)
    set_state(tg_user, 'pay.picking_doc', party_id=customer_id, party_name=customer.name)
    items = choices.confirmed_sales_with_debt(customer_id) + [(0, "Umumiy to'lov (sotuvga bog'lamasdan)")]
    send_picker(call.message.chat.id, 'pay_doc', items, "Qarzli sotuvga bog'laysizmi?")


@register_callback('pay_sup')
def pick_party_supplier(call, tg_user):
    supplier_id = int(call.data.split(':', 1)[1])
    from apps.suppliers.models import Supplier
    supplier = Supplier.objects.get(pk=supplier_id)
    bot.answer_callback_query(call.id, supplier.name)
    set_state(tg_user, 'pay.picking_doc', party_id=supplier_id, party_name=supplier.name)
    items = choices.confirmed_purchases_with_debt(supplier_id) + [(0, "Umumiy to'lov (xaridga bog'lamasdan)")]
    send_picker(call.message.chat.id, 'pay_doc', items, "Qarzli xaridga bog'laysizmi?")


@register_callback('pay_doc')
def pick_doc(call, tg_user):
    doc_id = int(call.data.split(':', 1)[1])
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'pay.amount', doc_id=(doc_id or None))
    bot.send_message(call.message.chat.id, "To'lov summasi?", reply_markup=keyboards.cancel_only())


@register_state('pay.amount')
def on_amount(message, tg_user):
    amount = parse_decimal(message.text)
    if amount is None or amount <= 0:
        bot.send_message(message.chat.id, "Summa musbat bolishi kerak. Qayta kiriting:")
        return
    set_state(tg_user, 'pay.picking_type', amount=str(amount))
    send_picker(message.chat.id, 'pay_ptype', choices.PAYMENT_TYPES, "To'lov turi:")


@register_callback('pay_ptype')
def pick_payment_type(call, tg_user):
    code = call.data.split(':', 1)[1]
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'pay.date', payment_type=code)
    bot.send_message(
        call.message.chat.id, "Sana? ('bugun' yoki 31.01.2026 ko'rinishida, o'tkazib yuborish = bugun)",
        reply_markup=keyboards.cancel_and_skip(),
    )


@register_state('pay.date')
def on_date(message, tg_user):
    from django.utils import timezone
    if is_skip(message.text):
        d = timezone.localdate()
    else:
        d = parse_date(message.text)
        if d is None:
            bot.send_message(message.chat.id, "Sana tushunarsiz. Qayta kiriting yoki o'tkazib yuboring:")
            return
    set_state(tg_user, 'pay.notes', date=d.isoformat())
    bot.send_message(message.chat.id, 'Izoh? (ixtiyoriy)', reply_markup=keyboards.cancel_and_skip())


@register_state('pay.notes')
def on_notes(message, tg_user):
    notes = '' if is_skip(message.text) else message.text.strip()
    set_state(tg_user, 'pay.confirm', notes=notes)
    _send_confirm(message.chat.id, tg_user)


def _send_confirm(chat_id, tg_user):
    data = tg_user.data
    party_label = 'Mijoz' if data['party_type'] == 'customer' else 'Yetkazib beruvchi'
    lines = [
        f'{party_label}: {data["party_name"]}',
        f"Summa: {som(data['amount'])}",
        f"To'lov turi: {dict(choices.PAYMENT_TYPES).get(data['payment_type'], data['payment_type'])}",
        f"Sana: {data['date']}",
    ]
    if data.get('notes'):
        lines.append(f"Izoh: {data['notes']}")
    lines.append('')
    lines.append('Tasdiqlaysizmi?')
    bot.send_message(chat_id, '\n'.join(lines), reply_markup=keyboards.confirm_cancel_inline('payconfirm:1'))


@register_callback('payconfirm')
def confirm_payment(call, tg_user):
    bot.answer_callback_query(call.id, 'Yuborildi...')
    data = tg_user.data
    user = tg_user.django_user

    try:
        from apps.customers.models import Customer
        from apps.purchases.models import Purchase
        from apps.sales.models import Sale
        from apps.suppliers.models import Supplier

        customer = supplier = sale = purchase = None
        if data['party_type'] == 'customer':
            customer = Customer.objects.get(pk=data['party_id'])
            if data.get('doc_id'):
                sale = Sale.objects.get(pk=data['doc_id'])
        else:
            supplier = Supplier.objects.get(pk=data['party_id'])
            if data.get('doc_id'):
                purchase = Purchase.objects.get(pk=data['doc_id'])

        payment = payment_service.create_payment(
            amount=Decimal(data['amount']), payment_type=data['payment_type'], date=data['date'],
            notes=data.get('notes', ''), user=user,
            customer=customer, supplier=supplier, sale=sale, purchase=purchase,
        )
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id, f"✅ To'lov qo'shildi: {som(payment.amount)}",
            reply_markup=keyboards.main_menu(),
        )
    except ValidationError as exc:
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id, f"❌ Xatolik:\n{errors_to_text(exc)}",
            reply_markup=keyboards.main_menu(),
        )


@register_callback('paylist')
def list_payments(call, tg_user):
    bot.answer_callback_query(call.id)
    payments = Payment.objects.select_related('customer', 'supplier', 'sale', 'purchase').all()[:10]
    if not payments:
        bot.send_message(call.message.chat.id, "Hozircha to'lovlar yo'q.")
        return
    for p in payments:
        party = p.customer.name if p.customer else p.supplier.name
        text = f"{party} — {som(p.amount)} ({p.get_payment_type_display()})\n{p.date}"
        from telebot import types
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton('❌ Bekor qilish (o\'chirish)', callback_data=f'paycancel:{p.pk}'))
        bot.send_message(call.message.chat.id, text, reply_markup=kb)


@register_callback('paycancel')
def cancel_payment_cb(call, tg_user):
    payment_id = int(call.data.split(':', 1)[1])
    payment = Payment.objects.get(pk=payment_id)
    try:
        payment_service.delete_payment(payment, user=tg_user.django_user)
        bot.answer_callback_query(call.id, "To'lov o'chirildi.")
        bot.send_message(call.message.chat.id, "✅ To'lov o'chirildi.")
    except ValidationError as exc:
        bot.answer_callback_query(call.id, 'Xatolik!', show_alert=True)
        bot.send_message(call.message.chat.id, f'❌ {errors_to_text(exc)}')
