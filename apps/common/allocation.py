"""Umumiy summani (masalan qo'shimcha xarajatlar) bir nechta qatorga
(xarid item'lari, bo'laklash chiqishlari) ulush bo'yicha taqsimlash uchun
umumiy yordamchi. `butchering_service`dagi taqsimot mantig'idan chiqarilgan —
xarid xarajatlarini kg bo'yicha, bo'laklash xarajatlarini son bo'yicha
taqsimlashda qayta ishlatiladi."""
from decimal import Decimal


def allocate_proportionally(total, rows, weight_fn, quantize=Decimal('0.01')):
    """`total`ni har bir qator uchun `weight_fn(row)` ulushi bo'yicha taqsimlaydi.

    Qaytaradi: {row: allocated_amount} lug'ati. Barcha vazn 0 bo'lsa (yoki
    `rows` bo'sh bo'lsa), summa qatorlar orasida teng taqsimlanadi.
    """
    rows = list(rows)
    if not rows or total is None:
        return {}

    weights = [weight_fn(r) or Decimal('0') for r in rows]
    total_weight = sum(weights, Decimal('0'))

    result = {}
    if total_weight > 0:
        for row, w in zip(rows, weights):
            share = w / total_weight
            result[row] = (total * share).quantize(quantize)
    else:
        n = len(rows)
        equal_share = (total / n).quantize(quantize) if n else Decimal('0')
        result = {row: equal_share for row in rows}
    return result
