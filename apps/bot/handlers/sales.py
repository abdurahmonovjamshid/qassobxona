"""Sotuv (Sale) oqimi: mijoz -> sana -> to'lov muddati (ixtiyoriy) -> N x
(mahsulot, miqdor, narx, chegirma, dona) -> boshlang'ich to'lov -> tasdiqlash.

`apps/sales/views.py::sale_create` bilan bir xil: DRAFT Sale + items bitta
`transaction.atomic()` blokida saqlanadi, so'ng `sale_service.confirm_sale()`
chaqiriladi (tannarx/ombordan chiqim/qoldiq yetarli emasligi tekshiruvi shu
servis ichida, o'zgarishsiz)."""
import io
import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

logger = logging.getLogger(__name__)

from apps.bot import choices, keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import errors_to_text, som
from apps.bot.handlers.common import register_menu
from apps.bot.inputs import is_skip, parse_decimal, parse_int
from apps.bot.pickers import register_calendar, register_pagination, send_calendar, send_picker
from apps.bot.state import register_callback, register_state, set_state
from apps.payments.services import payment_service
from apps.sales.models import Sale, SaleItem
from apps.sales.services import sale_service

register_pagination('s_cust', choices.active_customers)
register_pagination('s_prod', choices.active_products_with_stock)
register_pagination('s_ptype', lambda: choices.PAYMENT_TYPES)


@register_menu(keyboards.MENU_SALES)
def sales_menu(message, tg_user):
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('➕ Yangi sotuv', callback_data='snew:1'))
    kb.row(types.InlineKeyboardButton("📋 So'nggi sotuvlar", callback_data='slist:1'))
    kb.row(types.InlineKeyboardButton("⏰ Muddati o'tgan qarzlar", callback_data='sdue:1'))
    bot.send_message(message.chat.id, 'Sotuv bo\'limi:', reply_markup=kb)


@register_callback('snew')
def start_sale(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'sale.picking_customer', items=[])
    send_picker(call.message.chat.id, 's_cust', choices.active_customers(), 'Mijozni tanlang:')


@register_callback('s_cust')
def pick_customer(call, tg_user):
    customer_id = int(call.data.split(':', 1)[1])
    from apps.customers.models import Customer
    customer = Customer.objects.get(pk=customer_id)
    bot.answer_callback_query(call.id, customer.name)
    set_state(tg_user, 'sale.date', customer_id=customer_id, customer_name=customer.name)
    send_calendar(call.message.chat.id, 's_date', 'Sotuv sanasi?')


def _on_date_picked(call, tg_user, picked):
    set_state(tg_user, 'sale.due_date', date=picked.isoformat())
    from telebot import types
    send_calendar(
        call.message.chat.id, 's_due', "To'lov muddati (qarzga sotilsa)?",
        extra_rows=[[types.InlineKeyboardButton("🚫 Muddat yo'q", callback_data='s_due_none:1')]],
    )


register_calendar('s_date', _on_date_picked)


def _on_due_date_picked(call, tg_user, picked):
    set_state(tg_user, 'sale.picking_item', due_date=picked.isoformat())
    send_picker(call.message.chat.id, 's_prod', choices.active_products_with_stock(), 'Mahsulotni tanlang:')


register_calendar('s_due', _on_due_date_picked)


@register_callback('s_due_none')
def pick_no_due_date(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'sale.picking_item', due_date=None)
    send_picker(call.message.chat.id, 's_prod', choices.active_products_with_stock(), 'Mahsulotni tanlang:')


@register_callback('s_prod')
def pick_item_product(call, tg_user):
    product_id = int(call.data.split(':', 1)[1])
    from apps.products.models import Product
    product = Product.objects.get(pk=product_id)
    bot.answer_callback_query(call.id, product.name)
    set_state(
        tg_user, 'sale.item_qty',
        cur_product_id=product_id, cur_product_name=product.name, cur_default_price=str(product.sale_price),
    )
    bot.send_message(call.message.chat.id, f'{product.name} — necha kg?', reply_markup=keyboards.cancel_only())


@register_state('sale.item_qty')
def on_item_qty(message, tg_user):
    qty = parse_decimal(message.text)
    if qty is None or qty <= 0:
        bot.send_message(message.chat.id, 'Miqdor musbat son bolishi kerak. Qayta kiriting:')
        return
    set_state(tg_user, 'sale.item_price', cur_qty=str(qty))
    default_price = tg_user.data.get('cur_default_price', '0')
    bot.send_message(
        message.chat.id, f"Narx (so'm/kg)? (standart: {som(default_price)}, o'tkazib yuborsangiz shu qo'llanadi)",
        reply_markup=keyboards.cancel_and_skip(),
    )


@register_state('sale.item_price')
def on_item_price(message, tg_user):
    if is_skip(message.text):
        price = Decimal(tg_user.data.get('cur_default_price', '0'))
    else:
        price = parse_decimal(message.text)
        if price is None or price < 0:
            bot.send_message(message.chat.id, "Narx manfiy bo'lmasligi kerak. Qayta kiriting yoki o'tkazib yuboring:")
            return
    set_state(tg_user, 'sale.item_discount', cur_price=str(price))
    bot.send_message(message.chat.id, 'Chegirma? (ixtiyoriy, summa ko\'rinishida)', reply_markup=keyboards.cancel_and_skip())


@register_state('sale.item_discount')
def on_item_discount(message, tg_user):
    if is_skip(message.text):
        discount = Decimal('0')
    else:
        discount = parse_decimal(message.text)
        if discount is None or discount < 0:
            bot.send_message(message.chat.id, "Chegirma manfiy bo'lmasligi kerak. Qayta kiriting yoki o'tkazib yuboring:")
            return
    set_state(tg_user, 'sale.item_pieces', cur_discount=str(discount))
    bot.send_message(message.chat.id, "Necha dona/bo'lak? (ixtiyoriy)", reply_markup=keyboards.cancel_and_skip())


@register_state('sale.item_pieces')
def on_item_pieces(message, tg_user):
    if is_skip(message.text):
        pieces = 0
    else:
        pieces = parse_int(message.text)
        if pieces is None or pieces < 0:
            bot.send_message(message.chat.id, "Dona soni manfiy bo'lmasligi kerak. Qayta kiriting yoki o'tkazib yuboring:")
            return

    data = dict(tg_user.data)
    items = list(data.get('items', []))
    items.append({
        'product_id': data['cur_product_id'],
        'product_name': data['cur_product_name'],
        'quantity': data['cur_qty'],
        'price': data['cur_price'],
        'discount': data['cur_discount'],
        'pieces': pieces,
    })
    for key in ('cur_product_id', 'cur_product_name', 'cur_default_price', 'cur_qty', 'cur_price', 'cur_discount', 'items'):
        data.pop(key, None)
    set_state(tg_user, 'sale.picking_item', **data, items=items)

    bot.send_message(message.chat.id, _cart_text(items))
    bot.send_message(
        message.chat.id, 'Davom etamizmi?',
        reply_markup=keyboards.add_more_or_done('sitem_more:1', 'sitem_done:1'),
    )


def _cart_text(items):
    lines = ['Hozirgi savatcha:']
    total = Decimal('0')
    for it in items:
        line_total = Decimal(it['quantity']) * Decimal(it['price']) - Decimal(it['discount'])
        total += line_total
        lines.append(f"- {it['product_name']}: {it['quantity']} kg x {som(it['price'])} = {som(line_total)}")
    lines.append(f'Jami: {som(total)}')
    return '\n'.join(lines)


@register_callback('sitem_more')
def item_more(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'sale.picking_item')
    send_picker(call.message.chat.id, 's_prod', choices.active_products_with_stock(), 'Mahsulotni tanlang:')


@register_callback('sitem_done')
def item_done(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'sale.payment_amount')
    bot.send_message(
        call.message.chat.id, "Boshlang'ich to'lov summasi? (ixtiyoriy, o'tkazib yuborish = to'lovsiz)",
        reply_markup=keyboards.cancel_and_skip(),
    )


@register_state('sale.payment_amount')
def on_payment_amount(message, tg_user):
    if is_skip(message.text):
        set_state(tg_user, 'sale.confirm', paid_amount='0', payment_type='')
        _send_confirm(message.chat.id, tg_user)
        return
    amount = parse_decimal(message.text)
    if amount is None or amount < 0:
        bot.send_message(message.chat.id, "Summa manfiy bo'lmasligi kerak. Qayta kiriting yoki o'tkazib yuboring:")
        return
    if amount == 0:
        set_state(tg_user, 'sale.confirm', paid_amount='0', payment_type='')
        _send_confirm(message.chat.id, tg_user)
        return
    set_state(tg_user, 'sale.picking_payment_type', paid_amount=str(amount))
    send_picker(message.chat.id, 's_ptype', choices.PAYMENT_TYPES, "To'lov turi:")


@register_callback('s_ptype')
def pick_payment_type(call, tg_user):
    code = call.data.split(':', 1)[1]
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'sale.confirm', payment_type=code)
    _send_confirm(call.message.chat.id, tg_user)


def _send_confirm(chat_id, tg_user):
    data = tg_user.data
    lines = [
        f"Mijoz: {data['customer_name']}",
        f"Sana: {data['date']}",
    ]
    if data.get('due_date'):
        lines.append(f"To'lov muddati: {data['due_date']}")
    lines.append('')
    lines.append(_cart_text(data.get('items', [])))
    paid = Decimal(data.get('paid_amount', '0'))
    if paid > 0:
        lines.append(f"Boshlang'ich to'lov: {som(paid)}")
    lines.append('')
    lines.append('Tasdiqlaysizmi?')
    bot.send_message(chat_id, '\n'.join(lines), reply_markup=keyboards.confirm_cancel_inline('sconfirm:1'))


@register_callback('sconfirm')
def confirm_sale(call, tg_user):
    bot.answer_callback_query(call.id, 'Yuborildi...')
    data = tg_user.data
    user = tg_user.django_user
    try:
        with transaction.atomic():
            from apps.customers.models import Customer
            sale = Sale.objects.create(
                customer=Customer.objects.get(pk=data['customer_id']),
                sale_number=sale_service.generate_sale_number(),
                date=data['date'],
                due_date=data.get('due_date'),
                status=Sale.Status.DRAFT,
                created_by=user,
            )
            for it in data.get('items', []):
                SaleItem.objects.create(
                    sale=sale, product_id=it['product_id'],
                    quantity=Decimal(it['quantity']), pieces=it.get('pieces', 0),
                    price=Decimal(it['price']), discount=Decimal(it['discount']),
                )
            sale_service.confirm_sale(sale, user=user)

            paid_amount = Decimal(data.get('paid_amount', '0'))
            if paid_amount > 0:
                payment_service.create_payment(
                    amount=paid_amount, payment_type=data.get('payment_type') or 'CASH',
                    date=sale.date, customer=sale.customer, sale=sale, user=user,
                )
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id,
            f"✅ Sotuv {sale.sale_number} tasdiqlandi.\n"
            f"Jami: {som(sale.total_amount)}\nQarz: {som(sale.debt_amount)}",
            reply_markup=keyboards.main_menu(),
        )
    except ValidationError as exc:
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id,
            f"❌ Xatolik:\n{errors_to_text(exc)}\n\nQaytadan urinib ko'ring.",
            reply_markup=keyboards.main_menu(),
        )


@register_callback('slist')
def list_sales(call, tg_user):
    bot.answer_callback_query(call.id)
    send_calendar(call.message.chat.id, 'sl_date', "Qaysi sana uchun sotuvlar ro'yxati kerak?")


def _on_list_date_picked(call, tg_user, picked):
    sales = (
        Sale.objects.select_related('customer')
        .filter(date=picked, status=Sale.Status.CONFIRMED)
        .order_by('-id')[:30]
    )
    if not sales:
        bot.send_message(call.message.chat.id, f"{picked.strftime('%d.%m.%Y')} sanasida tasdiqlangan sotuvlar yo'q.")
        return
    from telebot import types
    from apps.common.pdf_documents import build_sale_pdf

    for s in sales:
        text = (
            f"{s.sale_number} — {s.customer.name}\n"
            f"{s.date} | {s.get_status_display()}\n"
            f"Jami: {som(s.total_amount)} | Qarz: {som(s.debt_amount)}"
        )
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton('❌ Bekor qilish', callback_data=f'scancel:{s.pk}'))
        bot.send_message(call.message.chat.id, text, reply_markup=kb)
        try:
            pdf_bytes = build_sale_pdf(s)
        except Exception:
            logger.exception('Sotuv nakladnoy PDF yaratib bolmadi: %s', s.sale_number)
            continue
        bot.send_document(call.message.chat.id, io.BytesIO(pdf_bytes), visible_file_name=f'{s.sale_number}.pdf')


register_calendar('sl_date', _on_list_date_picked)


@register_callback('scancel')
def cancel_sale_cb(call, tg_user):
    sale_id = int(call.data.split(':', 1)[1])
    sale = Sale.objects.get(pk=sale_id)
    try:
        sale_service.cancel_sale(sale, user=tg_user.django_user)
        bot.answer_callback_query(call.id, f'{sale.sale_number} bekor qilindi.')
        bot.send_message(call.message.chat.id, f"✅ Sotuv {sale.sale_number} bekor qilindi.")
    except ValidationError as exc:
        bot.answer_callback_query(call.id, 'Xatolik!', show_alert=True)
        bot.send_message(call.message.chat.id, f'❌ {errors_to_text(exc)}')


@register_callback('sdue')
def due_sales(call, tg_user):
    bot.answer_callback_query(call.id)
    sales = list(sale_service.get_due_sales())
    if not sales:
        bot.send_message(call.message.chat.id, "Muddati o'tgan qarzli sotuvlar yo'q.")
        return
    lines = ["⏰ Muddati o'tgan qarzli sotuvlar:", '']
    for s in sales[:30]:
        lines.append(f"{s.sale_number} — {s.customer.name} | muddat: {s.due_date} | qarz: {som(s.debt_amount)}")
    bot.send_message(call.message.chat.id, '\n'.join(lines))
