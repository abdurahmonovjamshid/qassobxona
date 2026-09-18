"""Bo'laklash (Butchering) oqimi: input mahsulot -> vazn -> dona ->
(ixtiyoriy) spetsifikatsiya -> sana -> N x output (mahsulot, miqdor, dona) ->
qo'shimcha xarajatlar -> tasdiqlash.

`apps/butchering/views.py::butchering_create` bilan bir xil: DRAFT
Butchering + outputs + expenses bitta `transaction.atomic()` blokida
saqlanadi, so'ng `butchering_service.confirm_butchering()` chaqiriladi —
input/output ombor harakatlari, ikki bosqichli tannarx taqsimoti (spetsifikatsiya
%/og'irlik ulushi + xarajatlarning dona ulushi) shu servis ichida, o'zgarishsiz."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.bot import choices, keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import date_fmt, errors_to_text, kg, som
from apps.bot.handlers.common import register_menu
from apps.bot.inputs import is_skip, parse_decimal, parse_int
from apps.bot.pickers import register_calendar, register_pagination, send_calendar, send_picker
from apps.bot.state import register_callback, register_state, set_state
from apps.butchering.models import Butchering, ButcheringExpense, ButcheringOutput
from apps.butchering.services import butchering_service
from apps.inventory.services import inventory_service

register_pagination('b_iprod', choices.butchering_input_products)
register_pagination('b_oprod', choices.active_products)
register_pagination('b_etype', lambda: choices.BUTCHERING_EXPENSE_TYPES)


@register_menu(keyboards.MENU_BUTCHERING)
def butchering_menu(message, tg_user):
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("➕ Yangi bo'laklash", callback_data='bnew:1'))
    kb.row(types.InlineKeyboardButton("📋 So'nggi bo'laklashlar", callback_data='blist:0'))
    bot.send_message(message.chat.id, "Bo'laklash bo'limi:", reply_markup=kb)


@register_callback('bnew')
def start_butchering(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'butch.picking_input', outputs=[], expenses=[])
    items = choices.butchering_input_products()
    if not items:
        bot.send_message(
            call.message.chat.id,
            "Bo'laklash uchun kamida bitta faol spetsifikatsiyaga ega mahsulot yo'q. "
            "Avval veb-saytda spetsifikatsiya yarating.",
        )
        tg_user.reset_state()
        return
    send_picker(call.message.chat.id, 'b_iprod', items, 'Qaysi mahsulot bo\'laklanadi?')


@register_callback('b_iprod')
def pick_input_product(call, tg_user):
    product_id = int(call.data.split(':', 1)[1])
    from apps.products.models import Product
    product = Product.objects.get(pk=product_id)
    stock = inventory_service.get_stock(product)
    bot.answer_callback_query(call.id, product.name)
    set_state(tg_user, 'butch.input_weight', input_product_id=product_id, input_product_name=product.name)
    bot.send_message(
        call.message.chat.id,
        f'{product.name} — necha kg bo\'laklanadi? (ombor qoldig\'i: {kg(stock)})',
        reply_markup=keyboards.cancel_only(),
    )


@register_state('butch.input_weight')
def on_input_weight(message, tg_user):
    weight = parse_decimal(message.text)
    if weight is None or weight <= 0:
        bot.send_message(message.chat.id, 'Vazn musbat son bolishi kerak. Qayta kiriting:')
        return
    set_state(tg_user, 'butch.input_pieces', input_weight=str(weight))
    bot.send_message(message.chat.id, "Necha dona/bo'lak? (ixtiyoriy)", reply_markup=keyboards.cancel_and_skip())


@register_state('butch.input_pieces')
def on_input_pieces(message, tg_user):
    if is_skip(message.text):
        pieces = 0
    else:
        pieces = parse_int(message.text)
        if pieces is None or pieces < 0:
            bot.send_message(message.chat.id, "Dona soni manfiy bo'lmasligi kerak. Qayta kiriting yoki o'tkazib yuboring:")
            return

    data = dict(tg_user.data)
    specs = choices.active_specifications(data['input_product_id'])
    set_state(tg_user, 'butch.picking_spec', input_pieces=pieces)
    if not specs:
        _ask_date(message.chat.id, tg_user)
        return
    items = specs + [(0, "❌ Spetsifikatsiyasiz (og'irlik ulushi)")]
    send_picker(message.chat.id, 'b_spec', items, 'Qaysi spetsifikatsiya (retsept) bo\'yicha?')


@register_callback('b_spec')
def pick_specification(call, tg_user):
    spec_id = int(call.data.split(':', 1)[1])
    bot.answer_callback_query(call.id)
    set_state(tg_user, tg_user.state, specification_id=(spec_id or None))
    _ask_date(call.message.chat.id, tg_user)


def _ask_date(chat_id, tg_user):
    set_state(tg_user, 'butch.date')
    send_calendar(chat_id, 'b_date', 'Sana?')


def _on_date_picked(call, tg_user, picked):
    set_state(tg_user, 'butch.picking_output', date=picked.isoformat())
    send_picker(call.message.chat.id, 'b_oprod', choices.active_products(), 'Chiqadigan mahsulotni tanlang:')


register_calendar('b_date', _on_date_picked)


@register_callback('b_oprod')
def pick_output_product(call, tg_user):
    product_id = int(call.data.split(':', 1)[1])
    from apps.products.models import Product
    product = Product.objects.get(pk=product_id)
    bot.answer_callback_query(call.id, product.name)
    set_state(tg_user, 'butch.output_qty', cur_output_product_id=product_id, cur_output_product_name=product.name)
    bot.send_message(call.message.chat.id, f'{product.name} — necha kg?', reply_markup=keyboards.cancel_only())


@register_state('butch.output_qty')
def on_output_qty(message, tg_user):
    qty = parse_decimal(message.text)
    if qty is None or qty <= 0:
        bot.send_message(message.chat.id, 'Miqdor musbat son bolishi kerak. Qayta kiriting:')
        return
    set_state(tg_user, 'butch.output_pieces', cur_output_qty=str(qty))
    bot.send_message(message.chat.id, "Necha dona/bo'lak? (ixtiyoriy)", reply_markup=keyboards.cancel_and_skip())


@register_state('butch.output_pieces')
def on_output_pieces(message, tg_user):
    if is_skip(message.text):
        pieces = 0
    else:
        pieces = parse_int(message.text)
        if pieces is None or pieces < 0:
            bot.send_message(message.chat.id, "Dona soni manfiy bo'lmasligi kerak. Qayta kiriting yoki o'tkazib yuboring:")
            return

    data = dict(tg_user.data)
    outputs = list(data.get('outputs', []))
    outputs.append({
        'product_id': data['cur_output_product_id'],
        'product_name': data['cur_output_product_name'],
        'quantity': data['cur_output_qty'],
        'pieces': pieces,
    })
    for key in ('cur_output_product_id', 'cur_output_product_name', 'cur_output_qty', 'outputs'):
        data.pop(key, None)
    set_state(tg_user, 'butch.picking_output', **data, outputs=outputs)

    bot.send_message(message.chat.id, _outputs_text(data['input_weight'], outputs))
    bot.send_message(
        message.chat.id, 'Davom etamizmi?',
        reply_markup=keyboards.add_more_or_done('boutput_more:1', 'boutput_done:1'),
    )


def _outputs_text(input_weight, outputs):
    lines = [f'Kirim: {kg(input_weight)}', 'Chiqishlar:']
    total = Decimal('0')
    for o in outputs:
        total += Decimal(o['quantity'])
        lines.append(f"- {o['product_name']}: {kg(o['quantity'])}")
    lines.append(f'Jami chiqish: {kg(total)} / {kg(input_weight)}')
    return '\n'.join(lines)


@register_callback('boutput_more')
def output_more(call, tg_user):
    bot.answer_callback_query(call.id)
    send_picker(call.message.chat.id, 'b_oprod', choices.active_products(), 'Chiqadigan mahsulotni tanlang:')


@register_callback('boutput_done')
def output_done(call, tg_user):
    bot.answer_callback_query(call.id)
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton('Ha', callback_data='bexp_yn:yes'),
        types.InlineKeyboardButton("Yo'q", callback_data='bexp_yn:no'),
    )
    bot.send_message(
        call.message.chat.id,
        "Qo'shimcha xarajat (ishchi kuchi, qadoqlash va h.k.) qo'shasizmi?",
        reply_markup=kb,
    )


@register_callback('bexp_yn')
def expense_yes_no(call, tg_user):
    bot.answer_callback_query(call.id)
    if call.data.endswith('no'):
        _send_confirm(call.message.chat.id, tg_user)
        return
    send_picker(call.message.chat.id, 'b_etype', choices.BUTCHERING_EXPENSE_TYPES, 'Xarajat turi:')


@register_callback('b_etype')
def pick_expense_type(call, tg_user):
    code = call.data.split(':', 1)[1]
    label = dict(choices.BUTCHERING_EXPENSE_TYPES).get(code, code)
    bot.answer_callback_query(call.id, label)
    set_state(tg_user, 'butch.expense_amount', cur_exp_type=code)
    bot.send_message(call.message.chat.id, f'{label} — summasi?', reply_markup=keyboards.cancel_only())


@register_state('butch.expense_amount')
def on_expense_amount(message, tg_user):
    amount = parse_decimal(message.text)
    if amount is None or amount < 0:
        bot.send_message(message.chat.id, "Summa manfiy bo'lmasligi kerak. Qayta kiriting:")
        return
    set_state(tg_user, 'butch.expense_notes', cur_exp_amount=str(amount))
    bot.send_message(message.chat.id, 'Izoh? (ixtiyoriy)', reply_markup=keyboards.cancel_and_skip())


@register_state('butch.expense_notes')
def on_expense_notes(message, tg_user):
    notes = '' if is_skip(message.text) else message.text.strip()
    data = dict(tg_user.data)
    expenses = list(data.get('expenses', []))
    expenses.append({'expense_type': data['cur_exp_type'], 'amount': data['cur_exp_amount'], 'notes': notes})
    for key in ('cur_exp_type', 'cur_exp_amount', 'expenses'):
        data.pop(key, None)
    set_state(tg_user, 'butch.picking_output', **data, expenses=expenses)

    total = sum((Decimal(e['amount']) for e in expenses), Decimal('0'))
    bot.send_message(message.chat.id, f"Xarajatlar jami: {som(total)} (naqd kassadan chiqim sifatida yoziladi)")
    bot.send_message(
        message.chat.id, "Yana xarajat qo'shamizmi?",
        reply_markup=keyboards.add_more_or_done('bexp_more:1', 'bexp_done:1'),
    )


@register_callback('bexp_more')
def expense_more(call, tg_user):
    bot.answer_callback_query(call.id)
    send_picker(call.message.chat.id, 'b_etype', choices.BUTCHERING_EXPENSE_TYPES, 'Xarajat turi:')


@register_callback('bexp_done')
def expense_done(call, tg_user):
    bot.answer_callback_query(call.id)
    _send_confirm(call.message.chat.id, tg_user)


def _send_confirm(chat_id, tg_user):
    data = tg_user.data
    lines = [
        f"Kiritilayotgan mahsulot: {data['input_product_name']}",
        f"Sana: {date_fmt(data['date'])}",
        '',
        _outputs_text(data['input_weight'], data.get('outputs', [])),
    ]
    expenses = data.get('expenses', [])
    if expenses:
        exp_total = sum((Decimal(e['amount']) for e in expenses), Decimal('0'))
        lines.append(f"Qo'shimcha xarajatlar: {som(exp_total)}")
    lines.append('')
    lines.append('Tasdiqlaysizmi?')
    bot.send_message(chat_id, '\n'.join(lines), reply_markup=keyboards.confirm_cancel_inline('bconfirm:1'))


@register_callback('bconfirm')
def confirm_butchering_cb(call, tg_user):
    bot.answer_callback_query(call.id, 'Yuborildi...')
    data = tg_user.data
    user = tg_user.django_user
    try:
        with transaction.atomic():
            butchering = Butchering.objects.create(
                input_product_id=data['input_product_id'],
                specification_id=data.get('specification_id'),
                input_weight=Decimal(data['input_weight']),
                input_pieces=data.get('input_pieces', 0),
                date=data['date'],
                status=Butchering.Status.DRAFT,
                created_by=user,
            )
            for o in data.get('outputs', []):
                ButcheringOutput.objects.create(
                    butchering=butchering, product_id=o['product_id'],
                    quantity=Decimal(o['quantity']), pieces=o.get('pieces', 0),
                )
            for exp in data.get('expenses', []):
                ButcheringExpense.objects.create(
                    butchering=butchering, expense_type=exp['expense_type'],
                    amount=Decimal(exp['amount']), notes=exp.get('notes', ''),
                )
            butchering_service.confirm_butchering(butchering, user=user)
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id,
            f"✅ Bo'laklash #{butchering.pk} tasdiqlandi.\n"
            f"Chiqish: {kg(butchering.output_weight)} / Kirim: {kg(butchering.input_weight)}\n"
            f"Farq: {kg(butchering.difference)} | Chiqim %: {butchering.yield_percentage}%",
            reply_markup=keyboards.main_menu(),
        )
    except ValidationError as exc:
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id,
            f"❌ Xatolik:\n{errors_to_text(exc)}\n\nQaytadan urinib ko'ring.",
            reply_markup=keyboards.main_menu(),
        )


@register_callback('blist')
def list_butcherings(call, tg_user):
    bot.answer_callback_query(call.id)
    items = Butchering.objects.select_related('input_product').all()[:10]
    if not items:
        bot.send_message(call.message.chat.id, "Hozircha bo'laklashlar yo'q.")
        return
    for b in items:
        text = (
            f"#{b.pk} — {b.input_product.name}\n"
            f"{date_fmt(b.date)} | {b.get_status_display()}\n"
            f"Kirim: {kg(b.input_weight)} | Chiqish: {kg(b.output_weight)} | Chiqim %: {b.yield_percentage}%"
        )
        from telebot import types
        kb = None
        if b.status == Butchering.Status.CONFIRMED:
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton('❌ Bekor qilish', callback_data=f'bcancel:{b.pk}'))
        bot.send_message(call.message.chat.id, text, reply_markup=kb)


@register_callback('bcancel')
def cancel_butchering_cb(call, tg_user):
    butchering_id = int(call.data.split(':', 1)[1])
    butchering = Butchering.objects.get(pk=butchering_id)
    try:
        butchering_service.cancel_butchering(butchering, user=tg_user.django_user)
        bot.answer_callback_query(call.id, f'#{butchering.pk} bekor qilindi.')
        bot.send_message(call.message.chat.id, f"✅ Bo'laklash #{butchering.pk} bekor qilindi.")
    except ValidationError as exc:
        bot.answer_callback_query(call.id, 'Xatolik!', show_alert=True)
        bot.send_message(call.message.chat.id, f'❌ {errors_to_text(exc)}')
