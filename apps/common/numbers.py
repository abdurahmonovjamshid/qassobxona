"""Butun loyihada (veb, bot, PDF) bir xil son formatlash qoidasi: minglik
qismi bo'sh joy bilan ajratiladi, ortiqcha kasr nollar (son butun bo'lsa —
kasr nuqtaning o'zi ham) ko'rsatilmaydi. Masalan: 1000000 -> "1 000 000",
1.500 -> "1.5", 1.000 -> "1"."""
from decimal import ROUND_HALF_UP, Decimal


def format_number(value, decimals=1) -> str:
    """Noto'g'ri/bo'sh qiymatlarda (masalan shablon o'zgaruvchisi topilmasa)
    Django'ning `floatformat`i kabi jim tarzda bo'sh satr qaytaradi — butun
    loyihada ko'plab shablon kontekstida ishlatilgani uchun xato ko'tarish
    o'rniga chidamli bo'lishi kerak."""
    if value is None:
        value = 0
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except (ArithmeticError, ValueError, TypeError):
            return ''

    quant = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
    value = value.quantize(quant, rounding=ROUND_HALF_UP)

    sign = '-' if value < 0 else ''
    int_part, _, frac_part = f'{abs(value):f}'.partition('.')
    frac_part = frac_part.rstrip('0')

    grouped_int = f'{int(int_part):,}'.replace(',', ' ')
    return f'{sign}{grouped_int}' + (f'.{frac_part}' if frac_part else '')


def format_money(value) -> str:
    return format_number(value, decimals=0)
