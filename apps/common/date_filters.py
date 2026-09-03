"""Ro'yxat sahifalari (sotuv, xarid, bo'laklash, to'lov, xarajat) uchun
umumiy sana-filtr yordamchisi.

Standart holatda (foydalanuvchi hech qanday sana bermaganda) joriy oy
boshidan bugungi kungacha bo'lgan oraliq qo'llaniladi — aks holda ro'yxat
har safar bazadagi BARCHA yozuvlarni yuklab, vaqt o'tishi bilan sahifani
sekinlashtirib qo'yardi.
"""
from django.utils import timezone


def get_date_range(request):
    """(date_from, date_to) ni ISO satr ko'rinishida qaytaradi.

    - `?all=1` bo'lsa — filtrsiz, ('', '') qaytaradi (butun tarix).
    - `date_from`/`date_to` dan biri berilgan bo'lsa — aynan shu qiymatlar
      qaytariladi (foydalanuvchi tanlagan oraliq).
    - Ikkalasi ham berilmagan bo'lsa — joriy oy boshidan bugungacha.
    """
    if request.GET.get('all') == '1':
        return '', ''

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if not date_from and not date_to:
        today = timezone.localdate()
        date_from = today.replace(day=1).isoformat()
        date_to = today.isoformat()
    return date_from, date_to
