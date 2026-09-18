"""Xarid (Purchase) oqimi: supplier -> sana -> N x (mahsulot, vazn, narx,
dona) -> qo'shimcha xarajatlar -> boshlang'ich to'lov -> tasdiqlash.

Yaratish `apps/purchases/views.py::purchase_create` bilan bir xil: DRAFT
Purchase + items + expenses bitta `transaction.atomic()` blokida saqlanadi,
so'ng `purchase_service.confirm_purchase()` chaqiriladi (ombor kirim va
landed-cost taqsimoti xuddi veb-saytdagidek shu servis ichida bo'ladi), va
agar boshlang'ich to'lov kiritilgan bo'lsa `payment_service.create_payment()`
chaqiriladi."""
import io
import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.bot import choices, keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import errors_to_text, kg
from apps.bot.formatters import pieces as pieces_fmt
from apps.bot.formatters import som
from apps.bot.handlers.common import register_menu
from apps.bot.inputs import is_skip, parse_decimal, parse_int
from apps.bot.pickers import register_calendar, register_pagination, send_calendar, send_picker
from apps.bot.state import register_callback, register_state, set_state
from apps.payments.services import payment_service
from apps.purchases.models import Purchase, PurchaseExpense, PurchaseItem
from apps.purchases.services import purchase_service

logger = logging.getLogger(__name__)

register_pagination('p_sup', choices.active_suppliers)
register_pagination('p_iprod', choices.active_products)
register_pagination('p_etype', lambda: choices.PURCHASE_EXPENSE_TYPES)
register_pagination('p_pay_type', lambda: choices.PAYMENT_TYPES)


@register_menu(keyboards.MENU_PURCHASES)
def purchases_menu(message, tg_user):
    bot.send_message(
        message.chat.id, "Xarid bo'limi:",
        reply_markup=_menu_inline(),
    )


def _menu_inline():
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('➕ Yangi xarid', callback_data='pnew:1'))
    kb.row(types.InlineKeyboardButton("📋 So'nggi xaridlar", callback_data='plist:1'))
    return kb


@register_callback('pnew')
def start_purchase(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'purchase.picking_supplier', items=[], expenses=[])
    send_picker(call.message.chat.id, 'p_sup', choices.active_suppliers(), "Yetkazib beruvchini tanlang:")


@register_callback('p_sup')
def pick_supplier(call, tg_user):
    supplier_id = int(call.data.split(':', 1)[1])
    from apps.suppliers.models import Supplier
    supplier = Supplier.objects.get(pk=supplier_id)
    bot.answer_callback_query(call.id, supplier.name)
    set_state(tg_user, 'purchase.date', supplier_id=supplier_id, supplier_name=supplier.name)
    send_calendar(call.message.chat.id, 'p_date', 'Xarid sanasi?')


def _on_date_picked(call, tg_user, picked):
    set_state(tg_user, 'purchase.picking_item', date=picked.isoformat())
    send_picker(call.message.chat.id, 'p_iprod', choices.active_products(), 'Mahsulotni tanlang:')


register_calendar('p_date', _on_date_picked)


@register_callback('p_iprod')
def pick_item_product(call, tg_user):
    product_id = int(call.data.split(':', 1)[1])
    from apps.products.models import Product
    product = Product.objects.get(pk=product_id)
    bot.answer_callback_query(call.id, product.name)
    set_state(tg_user, 'purchase.item_weight', cur_product_id=product_id, cur_product_name=product.name)
    bot.send_message(call.message.chat.id, f'{product.name} — necha kg?', reply_markup=keyboards.cancel_only())


@register_state('purchase.item_weight')
def on_item_weight(message, tg_user):
    weight = parse_decimal(message.text)
    if weight is None or weight <= 0:
        bot.send_message(message.chat.id, 'Vazn musbat son bolishi kerak. Qayta kiriting:')
        return
    set_state(tg_user, 'purchase.item_price', cur_weight=str(weight))
    bot.send_message(message.chat.id, 'Narx (so\'m/kg)?', reply_markup=keyboards.cancel_only())


@register_state('purchase.item_price')
def on_item_price(message, tg_user):
    price = parse_decimal(message.text)
    if price is None or price < 0:
        bot.send_message(message.chat.id, "Narx manfiy bo'lmasligi kerak. Qayta kiriting:")
        return
    set_state(tg_user, 'purchase.item_pieces', cur_price=str(price))
    bot.send_message(
        message.chat.id, 'Necha dona/bo\'lak? (ixtiyoriy)',
        reply_markup=keyboards.cancel_and_skip(),
    )


@register_state('purchase.item_pieces')
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
        'net_weight': data['cur_weight'],
        'price_per_kg': data['cur_price'],
        'pieces': pieces,
    })
    for key in ('cur_product_id', 'cur_product_name', 'cur_weight', 'cur_price', 'items'):
        data.pop(key, None)
    set_state(tg_user, 'purchase.picking_item', **data, items=items)

    bot.send_message(message.chat.id, _cart_text(items))
    bot.send_message(
        message.chat.id, 'Davom etamizmi?',
        reply_markup=keyboards.add_more_or_done('pitem_more:1', 'pitem_done:1'),
    )


def _cart_text(items):
    lines = ["Hozirgi savatcha:"]
    total = Decimal('0')
    for it in items:
        line_total = Decimal(it['net_weight']) * Decimal(it['price_per_kg'])
        total += line_total
        lines.append(f"- {it['product_name']}: {it['net_weight']} kg x {som(it['price_per_kg'])} = {som(line_total)}")
    lines.append(f'Jami: {som(total)}')
    return '\n'.join(lines)


@register_callback('pitem_more')
def item_more(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'purchase.picking_item')
    send_picker(call.message.chat.id, 'p_iprod', choices.active_products(), 'Mahsulotni tanlang:')


@register_callback('pitem_done')
def item_done(call, tg_user):
    bot.answer_callback_query(call.id)
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton('Ha', callback_data='pexp_yn:yes'),
        types.InlineKeyboardButton("Yo'q", callback_data='pexp_yn:no'),
    )
    bot.send_message(
        call.message.chat.id,
        "Qo'shimcha xarajat (transport, yuklash va h.k.) qo'shasizmi?",
        reply_markup=kb,
    )


@register_callback('pexp_yn')
def expense_yes_no(call, tg_user):
    bot.answer_callback_query(call.id)
    if call.data.endswith('no'):
        _ask_payment(call.message.chat.id, tg_user)
        return
    send_picker(call.message.chat.id, 'p_etype', choices.PURCHASE_EXPENSE_TYPES, 'Xarajat turi:')


@register_callback('p_etype')
def pick_expense_type(call, tg_user):
    code = call.data.split(':', 1)[1]
    label = dict(choices.PURCHASE_EXPENSE_TYPES).get(code, code)
    bot.answer_callback_query(call.id, label)
    set_state(tg_user, 'purchase.expense_amount', cur_exp_type=code)
    bot.send_message(call.message.chat.id, f'{label} — summasi?', reply_markup=keyboards.cancel_only())


@register_state('purchase.expense_amount')
def on_expense_amount(message, tg_user):
    amount = parse_decimal(message.text)
    if amount is None or amount < 0:
        bot.send_message(message.chat.id, "Summa manfiy bo'lmasligi kerak. Qayta kiriting:")
        return
    set_state(tg_user, 'purchase.expense_notes', cur_exp_amount=str(amount))
    bot.send_message(message.chat.id, 'Izoh? (ixtiyoriy)', reply_markup=keyboards.cancel_and_skip())


@register_state('purchase.expense_notes')
def on_expense_notes(message, tg_user):
    notes = '' if is_skip(message.text) else message.text.strip()
    data = dict(tg_user.data)
    expenses = list(data.get('expenses', []))
    expenses.append({'expense_type': data['cur_exp_type'], 'amount': data['cur_exp_amount'], 'notes': notes})
    for key in ('cur_exp_type', 'cur_exp_amount', 'expenses'):
        data.pop(key, None)
    set_state(tg_user, 'purchase.picking_item', **data, expenses=expenses)

    total = sum((Decimal(e['amount']) for e in expenses), Decimal('0'))
    bot.send_message(message.chat.id, f"Xarajatlar jami: {som(total)}")
    bot.send_message(
        message.chat.id, "Yana xarajat qo'shamizmi?",
        reply_markup=keyboards.add_more_or_done('pexp_more:1', 'pexp_done:1'),
    )


@register_callback('pexp_more')
def expense_more(call, tg_user):
    bot.answer_callback_query(call.id)
    send_picker(call.message.chat.id, 'p_etype', choices.PURCHASE_EXPENSE_TYPES, 'Xarajat turi:')


@register_callback('pexp_done')
def expense_done(call, tg_user):
    bot.answer_callback_query(call.id)
    _ask_payment(call.message.chat.id, tg_user)


def _ask_payment(chat_id, tg_user):
    set_state(tg_user, 'purchase.payment_amount')
    bot.send_message(
        chat_id, "Boshlang'ich to'lov summasi? (ixtiyoriy, o'tkazib yuborish = to'lovsiz)",
        reply_markup=keyboards.cancel_and_skip(),
    )


@register_state('purchase.payment_amount')
def on_payment_amount(message, tg_user):
    if is_skip(message.text):
        set_state(tg_user, 'purchase.confirm', paid_amount='0', payment_type='')
        _send_confirm(message.chat.id, tg_user)
        return
    amount = parse_decimal(message.text)
    if amount is None or amount < 0:
        bot.send_message(message.chat.id, "Summa manfiy bo'lmasligi kerak. Qayta kiriting yoki o'tkazib yuboring:")
        return
    if amount == 0:
        set_state(tg_user, 'purchase.confirm', paid_amount='0', payment_type='')
        _send_confirm(message.chat.id, tg_user)
        return
    set_state(tg_user, 'purchase.picking_payment_type', paid_amount=str(amount))
    send_picker(message.chat.id, 'p_etype2', choices.PAYMENT_TYPES, "To'lov turi:")


register_pagination('p_etype2', lambda: choices.PAYMENT_TYPES)


@register_callback('p_etype2')
def pick_payment_type(call, tg_user):
    code = call.data.split(':', 1)[1]
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'purchase.confirm', payment_type=code)
    _send_confirm(call.message.chat.id, tg_user)


def _send_confirm(chat_id, tg_user):
    data = tg_user.data
    lines = [
        f"Yetkazib beruvchi: {data['supplier_name']}",
        f"Sana: {data['date']}",
        '',
        _cart_text(data.get('items', [])),
    ]
    expenses = data.get('expenses', [])
    if expenses:
        exp_total = sum((Decimal(e['amount']) for e in expenses), Decimal('0'))
        lines.append(f"Qo'shimcha xarajatlar: {som(exp_total)}")
    paid = Decimal(data.get('paid_amount', '0'))
    if paid > 0:
        lines.append(f"Boshlang'ich to'lov: {som(paid)}")
    lines.append('')
    lines.append('Tasdiqlaysizmi?')
    bot.send_message(chat_id, '\n'.join(lines), reply_markup=keyboards.confirm_cancel_inline('pconfirm:1'))


@register_callback('pconfirm')
def confirm_purchase(call, tg_user):
    bot.answer_callback_query(call.id, 'Yuborildi...')
    data = tg_user.data
    user = tg_user.django_user
    try:
        with transaction.atomic():
            from apps.suppliers.models import Supplier
            purchase = Purchase.objects.create(
                supplier=Supplier.objects.get(pk=data['supplier_id']),
                purchase_number=purchase_service.generate_purchase_number(),
                date=data['date'],
                status=Purchase.Status.DRAFT,
                created_by=user,
            )
            for it in data.get('items', []):
                PurchaseItem.objects.create(
                    purchase=purchase, product_id=it['product_id'],
                    net_weight=Decimal(it['net_weight']), pieces=it.get('pieces', 0),
                    price_per_kg=Decimal(it['price_per_kg']),
                )
            for exp in data.get('expenses', []):
                PurchaseExpense.objects.create(
                    purchase=purchase, expense_type=exp['expense_type'],
                    amount=Decimal(exp['amount']), notes=exp.get('notes', ''),
                )
            purchase_service.confirm_purchase(purchase, user=user)

            paid_amount = Decimal(data.get('paid_amount', '0'))
            if paid_amount > 0:
                payment_service.create_payment(
                    amount=paid_amount, payment_type=data.get('payment_type') or 'CASH',
                    date=purchase.date, supplier=purchase.supplier, purchase=purchase, user=user,
                )
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id,
            f"✅ Xarid {purchase.purchase_number} tasdiqlandi.\n"
            f"Jami: {som(purchase.total_amount)}\nQarz: {som(purchase.debt_amount)}",
            reply_markup=keyboards.main_menu(),
        )
    except ValidationError as exc:
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id,
            f"❌ Xatolik:\n{errors_to_text(exc)}\n\nQaytadan urinib ko'ring.",
            reply_markup=keyboards.main_menu(),
        )


@register_callback('plist')
def list_purchases(call, tg_user):
    bot.answer_callback_query(call.id)
    send_calendar(call.message.chat.id, 'pl_date', "Qaysi sana uchun xaridlar ro'yxati kerak?")


def _on_list_date_picked(call, tg_user, picked):
    purchases = (
        Purchase.objects.select_related('supplier')
        .filter(date=picked, status=Purchase.Status.CONFIRMED)
        .order_by('-id')[:30]
    )
    if not purchases:
        bot.send_message(call.message.chat.id, f"{picked.strftime('%d.%m.%Y')} sanasida tasdiqlangan xaridlar yo'q.")
        return
    from telebot import types
    from apps.common.pdf_documents import build_purchase_pdf

    for p in purchases:
        lines = [
            f"{p.purchase_number} — {p.supplier.name}",
            f"{p.date} | {p.get_status_display()}",
            '',
            'Mahsulotlar:',
        ]
        for item in p.items.select_related('product').all():
            lines.append(
                f'• {item.product.name} — {kg(item.net_weight)}, {pieces_fmt(item.pieces)} '
                f'× {som(item.price_per_kg)} = {som(item.total)}'
            )
        lines += [
            '',
            f'Jami: {som(p.total_amount)} | Qarz: {som(p.debt_amount)}',
        ]
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton('❌ Bekor qilish', callback_data=f'pcancel:{p.pk}'),
            types.InlineKeyboardButton("💵 To'lov kiritish", callback_data=f'ppay:{p.pk}'),
        )
        sent = bot.send_message(call.message.chat.id, '\n'.join(lines), reply_markup=kb)
        try:
            pdf_bytes = build_purchase_pdf(p)
        except Exception:
            logger.exception('Xarid nakladnoy PDF yaratib bolmadi: %s', p.purchase_number)
            continue
        bot.send_document(
            call.message.chat.id, io.BytesIO(pdf_bytes), visible_file_name=f'{p.purchase_number}.pdf',
            reply_to_message_id=sent.message_id,
        )


register_calendar('pl_date', _on_list_date_picked)


@register_callback('ppay')
def start_existing_purchase_payment(call, tg_user):
    purchase_id = int(call.data.split(':', 1)[1])
    purchase = Purchase.objects.get(pk=purchase_id)
    bot.answer_callback_query(call.id)
    if purchase.debt_amount <= 0:
        bot.send_message(call.message.chat.id, "Bu xaridda qarz yo'q.")
        return
    set_state(tg_user, 'purchase.pay_existing_amount', pay_purchase_id=purchase_id)
    bot.send_message(
        call.message.chat.id, f"To'lov summasi? (Qarz: {som(purchase.debt_amount)})",
        reply_markup=keyboards.cancel_only(),
    )


@register_state('purchase.pay_existing_amount')
def on_pay_existing_amount(message, tg_user):
    amount = parse_decimal(message.text)
    if amount is None or amount <= 0:
        bot.send_message(message.chat.id, "Summa musbat bo'lishi kerak. Qayta kiriting:")
        return
    set_state(tg_user, 'purchase.pay_existing_type', pay_amount=str(amount))
    send_picker(message.chat.id, 'p_pay_type', choices.PAYMENT_TYPES, "To'lov turi:")


@register_callback('p_pay_type')
def pick_existing_purchase_payment_type(call, tg_user):
    code = call.data.split(':', 1)[1]
    bot.answer_callback_query(call.id)
    data = tg_user.data
    purchase = Purchase.objects.get(pk=data['pay_purchase_id'])
    amount = Decimal(data['pay_amount'])
    try:
        payment_service.create_payment(
            amount=amount, payment_type=code, date=purchase.date,
            supplier=purchase.supplier, purchase=purchase, user=tg_user.django_user,
        )
        tg_user.reset_state()
        purchase.refresh_from_db()
        bot.send_message(
            call.message.chat.id,
            f"✅ To'lov qabul qilindi.\nQolgan qarz: {som(purchase.debt_amount)}",
            reply_markup=keyboards.main_menu(),
        )
    except ValidationError as exc:
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id, f"❌ Xatolik:\n{errors_to_text(exc)}",
            reply_markup=keyboards.main_menu(),
        )


@register_callback('pcancel')
def cancel_purchase_cb(call, tg_user):
    purchase_id = int(call.data.split(':', 1)[1])
    purchase = Purchase.objects.get(pk=purchase_id)
    try:
        purchase_service.cancel_purchase(purchase, user=tg_user.django_user)
        bot.answer_callback_query(call.id, f'{purchase.purchase_number} bekor qilindi.')
        bot.send_message(call.message.chat.id, f"✅ Xarid {purchase.purchase_number} bekor qilindi.")
    except ValidationError as exc:
        bot.answer_callback_query(call.id, 'Xatolik!', show_alert=True)
        bot.send_message(call.message.chat.id, f'❌ {errors_to_text(exc)}')
