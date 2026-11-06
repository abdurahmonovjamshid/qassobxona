"""Ombor: joriy qoldiq (har bir ombor bo'yicha), harakatlar tarixi va
omborlar orasida ko'chirish.
`apps/inventory/views.py` bilan bir xil hisob-kitob —
`inventory_service.get_stock`/`get_stock_pieces`/`get_weighted_average_cost`
orqali, StockMovement to'g'ridan-to'g'ri o'qilmaydi. Ko'chirish esa
`apps/inventory/views.py::transfer_create` kabi DRAFT StockTransfer + items
saqlanib, `inventory_service.confirm_transfer()` chaqiriladi."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import date_fmt, errors_to_text, kg, som
from apps.bot.handlers.common import register_menu
from apps.bot.inputs import is_skip, parse_decimal, parse_int
from apps.bot.pickers import register_calendar, register_pagination, send_calendar, send_picker
from apps.bot.state import register_callback, register_state, set_state
from apps.bot.warehouses import active_warehouses
from apps.inventory.models import StockMovement, StockTransfer, StockTransferItem, Warehouse
from apps.inventory.services import inventory_service


@register_menu(keyboards.MENU_INVENTORY)
def inventory_menu(message, tg_user):
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('📦 Qoldiq', callback_data='invstock:1'))
    kb.row(types.InlineKeyboardButton("🔁 Omborlar orasida ko'chirish", callback_data='trnew:1'))
    kb.row(types.InlineKeyboardButton('📜 Harakatlar tarixi', callback_data='invmove:1'))
    bot.send_message(message.chat.id, 'Ombor bo\'limi:', reply_markup=kb)


@register_callback('invstock')
def stock(call, tg_user):
    bot.answer_callback_query(call.id)
    from apps.products.models import Product
    warehouses = list(Warehouse.objects.filter(active=True))
    kg_maps = {w.id: inventory_service.get_all_stock(w) for w in warehouses}
    pcs_maps = {w.id: inventory_service.get_all_stock_pieces(w) for w in warehouses}

    lines = ['📦 Ombor qoldig\'i:']
    for warehouse in warehouses:
        lines += ['', f'🏬 {warehouse.name}:']
        total = Decimal('0')
        for product in Product.objects.filter(active=True).order_by('name'):
            qty = kg_maps[warehouse.id].get(product.id, 0)
            pieces = pcs_maps[warehouse.id].get(product.id, 0)
            if not qty and not pieces:
                continue
            total += qty
            extra = f', {pieces} dona' if pieces else ''
            avg_cost = inventory_service.get_weighted_average_cost(product)
            lines.append(f'{product.name}: {kg(qty)}{extra} (o\'rt. tannarx {som(avg_cost)}/kg)')
        lines.append(f'Jami: {kg(total)}')
    bot.send_message(call.message.chat.id, '\n'.join(lines))


@register_callback('invmove')
def movements(call, tg_user):
    bot.answer_callback_query(call.id)
    moves = StockMovement.objects.select_related('product', 'warehouse').all()[:20]
    if not moves:
        bot.send_message(call.message.chat.id, "Hozircha ombor harakatlari yo'q.")
        return
    lines = ["📜 So'nggi ombor harakatlari:", '']
    for m in moves:
        sign = '+' if m.direction == StockMovement.Direction.IN else '-'
        lines.append(
            f'{date_fmt(m.date)} [{m.warehouse.name}] {m.product.name}: '
            f'{sign}{kg(m.quantity)} ({m.get_movement_type_display()})'
        )
    bot.send_message(call.message.chat.id, '\n'.join(lines))


# --- Omborlar orasida ko'chirish ---

def _products_in_warehouse(tg_user):
    """Faqat "qaysi ombordan" omborida qoldig'i bor mahsulotlar."""
    from apps.products.models import Product
    warehouse_id = (tg_user.data or {}).get('from_warehouse_id')
    warehouse = Warehouse.objects.filter(pk=warehouse_id).first()
    stock_map = inventory_service.get_all_stock(warehouse)
    pcs_map = inventory_service.get_all_stock_pieces(warehouse)
    items = []
    for p in Product.objects.filter(active=True).order_by('name'):
        qty, pcs = stock_map.get(p.id, 0), pcs_map.get(p.id, 0)
        if qty > 0 or pcs > 0:
            extra = f', {pcs} dona' if pcs else ''
            items.append((p.id, f'{p.name} ({qty} kg{extra})'))
    return items


register_pagination('tr_from', active_warehouses)
register_pagination(
    'tr_to',
    lambda tg_user: [(w_id, name) for w_id, name in active_warehouses()
                     if w_id != (tg_user.data or {}).get('from_warehouse_id')],
    needs_user=True,
)
register_pagination('tr_prod', _products_in_warehouse, needs_user=True)


@register_callback('trnew')
def start_transfer(call, tg_user):
    bot.answer_callback_query(call.id)
    warehouses = active_warehouses()
    if len(warehouses) < 2:
        bot.send_message(call.message.chat.id, "Ko'chirish uchun kamida 2 ta faol ombor kerak.")
        return
    set_state(tg_user, 'transfer.from', items=[])
    send_picker(call.message.chat.id, 'tr_from', warehouses, 'Qaysi ombordan?')


@register_callback('tr_from')
def pick_from(call, tg_user):
    warehouse = Warehouse.objects.get(pk=int(call.data.split(':', 1)[1]))
    bot.answer_callback_query(call.id, warehouse.name)
    set_state(tg_user, 'transfer.to', from_warehouse_id=warehouse.id, from_warehouse_name=warehouse.name)
    others = [(w_id, name) for w_id, name in active_warehouses() if w_id != warehouse.id]
    if len(others) == 1:
        _set_to(call.message.chat.id, tg_user, *others[0])
        return
    send_picker(call.message.chat.id, 'tr_to', others, 'Qaysi omborga?')


@register_callback('tr_to')
def pick_to(call, tg_user):
    warehouse = Warehouse.objects.get(pk=int(call.data.split(':', 1)[1]))
    bot.answer_callback_query(call.id, warehouse.name)
    _set_to(call.message.chat.id, tg_user, warehouse.id, warehouse.name)


def _set_to(chat_id, tg_user, warehouse_id, warehouse_name):
    set_state(tg_user, 'transfer.date', to_warehouse_id=warehouse_id, to_warehouse_name=warehouse_name)
    bot.send_message(chat_id, f"Qayerga: {warehouse_name}")
    send_calendar(chat_id, 'tr_date', "Ko'chirish sanasi?")


def _on_date_picked(call, tg_user, picked):
    set_state(tg_user, 'transfer.picking_item', date=picked.isoformat())
    _send_product_picker(call.message.chat.id, tg_user)


register_calendar('tr_date', _on_date_picked)


def _send_product_picker(chat_id, tg_user):
    items = _products_in_warehouse(tg_user)
    if not items:
        bot.send_message(chat_id, f"{tg_user.data.get('from_warehouse_name')}da qoldig'i bor mahsulot yo'q.",
                         reply_markup=keyboards.main_menu())
        tg_user.reset_state()
        return
    send_picker(chat_id, 'tr_prod', items, "Qaysi mahsulot ko'chiriladi?")


@register_callback('tr_prod')
def pick_product(call, tg_user):
    from apps.products.models import Product
    product = Product.objects.get(pk=int(call.data.split(':', 1)[1]))
    bot.answer_callback_query(call.id, product.name)
    warehouse = Warehouse.objects.get(pk=tg_user.data['from_warehouse_id'])
    available = inventory_service.get_stock(product, warehouse)
    set_state(tg_user, 'transfer.item_qty', cur_product_id=product.id, cur_product_name=product.name)
    bot.send_message(
        call.message.chat.id, f'{product.name} — necha kg? (qoldiq: {kg(available)})',
        reply_markup=keyboards.cancel_only(),
    )


@register_state('transfer.item_qty')
def on_item_qty(message, tg_user):
    qty = parse_decimal(message.text)
    if qty is None or qty < 0:
        bot.send_message(message.chat.id, 'Miqdor manfiy bolmasligi kerak. Qayta kiriting:')
        return
    set_state(tg_user, 'transfer.item_pieces', cur_qty=str(qty))
    bot.send_message(message.chat.id, "Necha dona/bo'lak? (ixtiyoriy)", reply_markup=keyboards.cancel_and_skip())


@register_state('transfer.item_pieces')
def on_item_pieces(message, tg_user):
    if is_skip(message.text):
        pieces = 0
    else:
        pieces = parse_int(message.text)
        if pieces is None or pieces < 0:
            bot.send_message(message.chat.id, "Dona soni manfiy bo'lmasligi kerak. Qayta kiriting yoki o'tkazib yuboring:")
            return
    data = dict(tg_user.data)
    if Decimal(data['cur_qty']) == 0 and pieces == 0:
        bot.send_message(message.chat.id, "Kg yoki dona sonidan kamida bittasi musbat bo'lishi kerak.")
        set_state(tg_user, 'transfer.item_qty')
        bot.send_message(message.chat.id, f"{data['cur_product_name']} — necha kg?", reply_markup=keyboards.cancel_only())
        return
    items = list(data.get('items', []))
    items.append({
        'product_id': data['cur_product_id'], 'product_name': data['cur_product_name'],
        'quantity': data['cur_qty'], 'pieces': pieces,
    })
    set_state(tg_user, 'transfer.picking_item', items=items)
    bot.send_message(message.chat.id, _items_text(items))
    bot.send_message(
        message.chat.id, 'Davom etamizmi?',
        reply_markup=keyboards.add_more_or_done('tritem_more:1', 'tritem_done:1'),
    )


def _items_text(items):
    lines = ["Ko'chiriladigan mahsulotlar:"]
    for it in items:
        extra = f" ({it['pieces']} dona)" if it.get('pieces') else ''
        lines.append(f"- {it['product_name']}: {it['quantity']} kg{extra}")
    return '\n'.join(lines)


@register_callback('tritem_more')
def item_more(call, tg_user):
    bot.answer_callback_query(call.id)
    set_state(tg_user, 'transfer.picking_item')
    _send_product_picker(call.message.chat.id, tg_user)


@register_callback('tritem_done')
def item_done(call, tg_user):
    bot.answer_callback_query(call.id)
    data = tg_user.data
    set_state(tg_user, 'transfer.confirm')
    lines = [
        f"Qayerdan: {data['from_warehouse_name']}",
        f"Qayerga: {data['to_warehouse_name']}",
        f"Sana: {date_fmt(data['date'])}",
        '',
        _items_text(data.get('items', [])),
        '',
        'Tasdiqlaysizmi?',
    ]
    bot.send_message(call.message.chat.id, '\n'.join(lines), reply_markup=keyboards.confirm_cancel_inline('trconfirm:1'))


@register_callback('trconfirm')
def confirm_transfer(call, tg_user):
    bot.answer_callback_query(call.id, 'Yuborildi...')
    data = tg_user.data
    user = tg_user.django_user
    try:
        with transaction.atomic():
            transfer = StockTransfer.objects.create(
                date=data['date'],
                from_warehouse_id=data['from_warehouse_id'],
                to_warehouse_id=data['to_warehouse_id'],
                status=StockTransfer.Status.DRAFT,
                created_by=user,
            )
            for it in data.get('items', []):
                StockTransferItem.objects.create(
                    transfer=transfer, product_id=it['product_id'],
                    quantity=Decimal(it['quantity']), pieces=it.get('pieces', 0),
                )
            inventory_service.confirm_transfer(transfer, user=user)
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id,
            f"✅ Ko'chirish #{transfer.pk} tasdiqlandi: {data['from_warehouse_name']} → {data['to_warehouse_name']}.",
            reply_markup=keyboards.main_menu(),
        )
    except ValidationError as exc:
        tg_user.reset_state()
        bot.send_message(
            call.message.chat.id,
            f"❌ Xatolik:\n{errors_to_text(exc)}\n\nQaytadan urinib ko'ring.",
            reply_markup=keyboards.main_menu(),
        )
