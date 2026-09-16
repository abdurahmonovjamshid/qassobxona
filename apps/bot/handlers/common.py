"""Botning "skeleti": /start, asosiy menyu marshrutlash, bekor qilish va
suhbat holati (FSM) dispatcheriga ulanish. Boshqa har bir modul o'zining
menyu tugmasini shu yerdagi `register_menu(...)` orqali ro'yxatdan o'tkazadi.

Bitta xabar uchun BITTA matn handleri va BITTA callback handleri bor (bir
nechta mos keluvchi handler ro'yxatdan o'tkazilganda pyTelegramBotAPI'ning
qaysi birini ishlatishi noaniqligini oldini olish uchun) — ichida navbat
bilan: /start -> "Bekor qilish" -> joriy FSM bosqichi -> menyu tugmasi ->
fallback."""
from apps.bot import keyboards
from apps.bot.bot_instance import bot
from apps.bot.models import TgUser
from apps.bot.state import dispatch_callback, dispatch_text

MENU_ROUTES = {}


def register_menu(text):
    def decorator(fn):
        MENU_ROUTES[text] = fn
        return fn
    return decorator


def get_tg_user(telegram_id) -> TgUser:
    return TgUser.objects.get(telegram_id=telegram_id)


def send_main_menu(chat_id, text="Asosiy menyu:"):
    bot.send_message(chat_id, text, reply_markup=keyboards.main_menu())


@bot.message_handler(content_types=['text'])
def on_text(message):
    tg_user = get_tg_user(message.from_user.id)

    if message.text == '/start':
        tg_user.reset_state()
        bot.send_message(
            message.chat.id,
            "Assalomu alaykum! Bu — Qassobxona boshqaruv boti.\n"
            "Quyidagi menyudan bo'lim tanlang.",
            reply_markup=keyboards.main_menu(),
        )
        return

    if message.text == keyboards.CANCEL_TEXT:
        tg_user.reset_state()
        send_main_menu(message.chat.id, 'Bekor qilindi.')
        return

    if tg_user.state and dispatch_text(message, tg_user):
        return

    menu_handler = MENU_ROUTES.get(message.text)
    if menu_handler:
        tg_user.reset_state()
        menu_handler(message, tg_user)
        return

    send_main_menu(message.chat.id, "Tushunmadim, quyidagi menyudan tanlang:")


@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    tg_user = get_tg_user(call.from_user.id)

    if call.data == 'noop:cancel':
        bot.answer_callback_query(call.id)
        tg_user.reset_state()
        send_main_menu(call.message.chat.id, 'Bekor qilindi.')
        return

    if call.data.startswith('noop:'):
        bot.answer_callback_query(call.id)
        return

    if dispatch_callback(call, tg_user):
        # Har bir callback handler o'zi bot.answer_callback_query(call.id, ...)
        # chaqiradi (ba'zan matnli toast bilan) — bu yerda qayta chaqirilmaydi,
        # aks holda Telegram "query allaqachon javob berilgan" xatosi beradi.
        return

    bot.answer_callback_query(call.id, "Noma'lum amal yoki muddati o'tgan tugma.")
