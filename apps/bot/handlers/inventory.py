"""Ombor (faqat o'qish uchun): joriy qoldiq va harakatlar tarixi.
`apps/inventory/views.py::inventory_list` bilan bir xil hisob-kitob —
`inventory_service.get_stock`/`get_stock_pieces`/`get_weighted_average_cost`
orqali, StockMovement to'g'ridan-to'g'ri o'qilmaydi."""
from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.formatters import kg, som
from apps.bot.handlers.common import register_menu
from apps.bot.state import register_callback
from apps.inventory.models import StockMovement
from apps.inventory.services import inventory_service


@register_menu(keyboards.MENU_INVENTORY)
def inventory_menu(message, tg_user):
    from telebot import types
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton('📦 Qoldiq', callback_data='invstock:1'))
    kb.row(types.InlineKeyboardButton('📜 Harakatlar tarixi', callback_data='invmove:1'))
    bot.send_message(message.chat.id, 'Ombor bo\'limi:', reply_markup=kb)


@register_callback('invstock')
def stock(call, tg_user):
    bot.answer_callback_query(call.id)
    from apps.products.models import Product
    rows = []
    for product in Product.objects.filter(active=True).order_by('name'):
        qty = inventory_service.get_stock(product)
        pieces = inventory_service.get_stock_pieces(product)
        avg_cost = inventory_service.get_weighted_average_cost(product)
        rows.append((product.name, qty, pieces, avg_cost))

    lines = ['📦 Ombor qoldig\'i:', '']
    total = 0
    for name, qty, pieces, avg_cost in rows:
        total += qty
        extra = f', {pieces} dona' if pieces else ''
        lines.append(f'{name}: {kg(qty)}{extra} (o\'rt. tannarx {som(avg_cost)}/kg)')
    lines.append('')
    lines.append(f'Jami: {kg(total)}')
    bot.send_message(call.message.chat.id, '\n'.join(lines))


@register_callback('invmove')
def movements(call, tg_user):
    bot.answer_callback_query(call.id)
    moves = StockMovement.objects.select_related('product').all()[:20]
    if not moves:
        bot.send_message(call.message.chat.id, "Hozircha ombor harakatlari yo'q.")
        return
    lines = ["📜 So'nggi ombor harakatlari:", '']
    for m in moves:
        sign = '+' if m.direction == StockMovement.Direction.IN else '-'
        lines.append(f'{m.date} {m.product.name}: {sign}{kg(m.quantity)} ({m.get_movement_type_display()})')
    bot.send_message(call.message.chat.id, '\n'.join(lines))
