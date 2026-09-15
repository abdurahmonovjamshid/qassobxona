"""Foydalanuvchi matn kiritmalarini parslash yordamchilari — hamma joyda bir
xil qabul qilinadigan formatlar uchun (sana, pul/vazn, butun son)."""
import re
from datetime import date, datetime
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


def parse_date(text):
    text = (text or '').strip().lower()
    if text in ('bugun', 'today', "hozir"):
        return date.today()
    for fmt in ('%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def is_skip(text) -> bool:
    from apps.bot.keyboards import SKIP_TEXT
    return (text or '').strip() == SKIP_TEXT
