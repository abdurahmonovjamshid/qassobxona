"""Shablonlarda son formatlash uchun: `{{ value|uzsum }}` (pul — butun son,
minglik bo'sh joy bilan) va `{{ value|uzqty }}` (og'irlik/miqdor/foiz — 1
kasr xonagacha, ortiqcha nollarsiz). `apps.common.numbers`dagi bitta qoidani
ishlatadi — bot va PDF hujjatlar bilan bir xil ko'rinish uchun."""
from django import template

from apps.common.numbers import format_money, format_number

register = template.Library()


@register.filter(name='uzsum')
def uzsum(value):
    return format_money(value)


@register.filter(name='uzqty')
def uzqty(value, decimals=1):
    return format_number(value, decimals=int(decimals))
