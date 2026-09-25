"""Ism ortiga yashirilgan buyruq havolalari.

Telegram matnida faqat `/buyruq` ko'rinishidagi so'z avtomatik bosiladigan
bo'ladi — ya'ni ismning o'zini bosiladigan qilishning yagona yo'li uni HTML
havolaga o'rash. Havola manzili sifatida botning o'z deep-link'i ishlatiladi:

    <a href="https://t.me/<bot>?start=sup_12">Abdulloh fermer</a>

Foydalanuvchi ismga bosganda Telegram botga `/start sup_12` yuboradi.
`handlers/common.py` shu xabarni tutib oladi, tegishli handlerga yo'naltiradi
va xabarning o'zini darhol o'chiradi — natijada suhbatda hech qanday buyruq
ko'rinmaydi, faqat ism va javob qoladi.

Bot username'i noma'lum bo'lsa (token sozlanmagan yoki tarmoq yo'q) ism
oddiy matn bo'lib qoladi va yoniga ochiq `/sup_12` qo'yiladi — shunda ham
ishlaydi, faqat chiroyliligi kamroq."""
import html
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_username_cache = None


def bot_username() -> str:
    """Bot username'i (bir marta aniqlanib, xotirada saqlanadi)."""
    global _username_cache
    if _username_cache is not None:
        return _username_cache

    _username_cache = (settings.TELEGRAM_BOT_USERNAME or '').lstrip('@')
    if not _username_cache and settings.TELEGRAM_BOT_TOKEN:
        try:
            from apps.bot.bot_instance import bot
            _username_cache = bot.get_me().username or ''
        except Exception:
            # Tarmoq xatosi butun ro'yxatni buzmasligi kerak — havolasiz
            # ko'rinishga tushib qolamiz.
            logger.warning("Bot username'ini aniqlab bo'lmadi, havolasiz rejim.", exc_info=True)
            _username_cache = ''
    return _username_cache


def partner_link(prefix: str, obj_id, label: str) -> str:
    """`label`ni bosiladigan havolaga o'raydi.

    `prefix` — `handlers/common.py::register_command` da ro'yxatdan o'tgan
    buyruq prefiksi ('sup' yoki 'mij')."""
    safe_label = html.escape(str(label))
    username = bot_username()
    if not username:
        return f'{safe_label} /{prefix}_{obj_id}'
    return f'<a href="https://t.me/{username}?start={prefix}_{obj_id}">{safe_label}</a>'


def customer_link(customer) -> str:
    return partner_link('mij', customer.id, customer.name)


def supplier_link(supplier) -> str:
    return partner_link('sup', supplier.id, supplier.name)
