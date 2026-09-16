"""Xabar matnlarida ishlatiladigan raqam formatlash yordamchilari — veb-sayt
shablonlaridagi (`uzsum`/`uzqty`) bilan bir xil qoida: `apps.common.numbers`."""
from apps.common.numbers import format_money, format_number


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
