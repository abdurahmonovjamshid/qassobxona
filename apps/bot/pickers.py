"""Bir nechta modulda takrorlanadigan "ro'yxatdan tanlash" UI'sini
markazlashtiradi: dastlabki xabar yuborish va sahifalash (pagination)
callback'ini ro'yxatdan o'tkazish."""
from datetime import date

from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.state import register_callback


def send_picker(chat_id, prefix, items, title, page=0, extra_rows=None):
    if not items:
        bot.send_message(chat_id, f'{title}\n\n(Ro\'yxat bo\'sh.)')
        return None
    return bot.send_message(
        chat_id, title,
        reply_markup=keyboards.picker(prefix, items, page=page, extra_rows=extra_rows),
    )


def register_pagination(prefix, items_fn):
    """Har bir modul o'z picker'ini import vaqtida shu bilan ro'yxatdan
    o'tkazadi — sahifalash tugmasi bosilganda ro'yxat qaytadan hisoblanadi
    va xabar shu joyida tahrirlanadi (yangi xabar yuborilmaydi)."""

    @register_callback(f'{prefix}_pg')
    def _paginate(call, tg_user):
        page = int(call.data.split(':', 1)[1])
        items = items_fn()
        bot.edit_message_reply_markup(
            call.message.chat.id, call.message.message_id,
            reply_markup=keyboards.picker(prefix, items, page=page),
        )
        bot.answer_callback_query(call.id)

    return _paginate


def send_calendar(chat_id, prefix, title, extra_rows=None):
    today = date.today()
    return bot.send_message(
        chat_id, title,
        reply_markup=keyboards.calendar_keyboard(prefix, today.year, today.month, extra_rows=extra_rows),
    )


def register_calendar(prefix, on_pick, extra_rows=None):
    """Oy grid'idan sana tanlashni ro'yxatdan o'tkazadi: oldinga/orqaga
    (`{prefix}_nav`) — xabar shu joyida tahrirlanadi, kun tanlash
    (`{prefix}`) — `on_pick(call, tg_user, picked_date)` chaqiriladi."""

    @register_callback(f'{prefix}_nav')
    def _nav(call, tg_user):
        year, month = (int(part) for part in call.data.split(':', 1)[1].split('-'))
        bot.edit_message_reply_markup(
            call.message.chat.id, call.message.message_id,
            reply_markup=keyboards.calendar_keyboard(prefix, year, month, extra_rows=extra_rows),
        )
        bot.answer_callback_query(call.id)

    @register_callback(prefix)
    def _pick(call, tg_user):
        picked = date.fromisoformat(call.data.split(':', 1)[1])
        bot.answer_callback_query(call.id)
        on_pick(call, tg_user, picked)

    return _pick
