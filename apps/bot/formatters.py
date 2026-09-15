"""Xabar matnlarida ishlatiladigan raqam formatlash yordamchilari — veb-sayt
shablonlaridagi (`humanize`) ko'rinishga yaqin: minglik ajratkichi bo'sh joy."""
from decimal import Decimal


def som(value) -> str:
    if value is None:
        value = Decimal('0')
    value = Decimal(value).quantize(Decimal('1'))
    sign = '-' if value < 0 else ''
    grouped = f'{abs(int(value)):,}'.replace(',', ' ')
    return f"{sign}{grouped} so'm"


def kg(value) -> str:
    if value is None:
        value = Decimal('0')
    value = Decimal(value)
    return f"{value:.3f} kg"


def pieces(value) -> str:
    return f"{int(value or 0)} dona"


def errors_to_text(exc) -> str:
    messages = getattr(exc, 'messages', None)
    if messages:
        return '\n'.join(f'- {m}' for m in messages)
    return str(exc)
