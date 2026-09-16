"""Foydalanuvchi matn kiritmalarini parslash yordamchilari — hamma joyda bir
xil qabul qilinadigan formatlar uchun (pul/vazn, butun son). Sana endi
matndan emas, inline calendar keyboard orqali tanlanadi (bot/keyboards.py
`calendar_keyboard`, bot/pickers.py `send_calendar`/`register_calendar`)."""
import re
from decimal import Decimal, InvalidOperation

_NUM_CLEAN_RE = re.compile(r'[^0-9.,-]')


def parse_decimal(text):
    if text is None:
        return None
    cleaned = _NUM_CLEAN_RE.sub('', text.strip())
    cleaned = cleaned.replace(' ', '').replace(',', '.')
    if not cleaned or cleaned in ('-', '.'):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_int(text):
    value = parse_decimal(text)
    if value is None:
        return None
    return int(value)


def is_skip(text) -> bool:
    from apps.bot.keyboards import SKIP_TEXT
    return (text or '').strip() == SKIP_TEXT
