"""Xabar matnlarida ishlatiladigan raqam formatlash yordamchilari — veb-sayt
shablonlaridagi (`uzsum`/`uzqty`) bilan bir xil qoida: `apps.common.numbers`."""
from datetime import date, datetime

from apps.common.numbers import format_money, format_number


def date_fmt(value) -> str:
    """Har qanday sana ko'rinishini (date/datetime obyekti yoki ISO satr
    'YYYY-MM-DD') veb-saytdagi kabi dd.mm.yyyy formatiga keltiradi."""
    if not value:
        return ''
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime('%d.%m.%Y')


def som(value) -> str:
    return f'{format_money(value)} so\'m'


def kg(value) -> str:
    return f'{format_number(value, decimals=1)} kg'


def pieces(value) -> str:
    return f"{int(value or 0)} dona"


def errors_to_text(exc) -> str:
    messages = getattr(exc, 'messages', None)
    if messages:
        return '\n'.join(f'- {m}' for m in messages)
    return str(exc)
