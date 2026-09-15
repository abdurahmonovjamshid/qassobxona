"""Bir nechta modulda takrorlanadigan "ro'yxatdan tanlash" UI'sini
markazlashtiradi: dastlabki xabar yuborish va sahifalash (pagination)
callback'ini ro'yxatdan o'tkazish."""
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
