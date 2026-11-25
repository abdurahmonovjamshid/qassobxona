"""Kunlik hisobotni tashqi taymer (cron-job.org) orqali ishga tushirish.

PythonAnywhere bepul tarifida rejali vazifalar yo'q, shuning uchun tashqi
xizmat har kuni maxfiy havolani ochadi. Kalit bot tokenidan hosil qilinadi —
.env'ga qo'shimcha narsa yozish shart emas. To'liq havolani olish:
    python manage.py daily_report --url
Bir kunda faqat bir marta yuboriladi (qayta urinishlar takrorlamaydi).
"""
import hashlib
import hmac

from django.conf import settings
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.utils import timezone


def daily_key():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return ''
    return hmac.new(token.encode(), b'daily-report', hashlib.sha256).hexdigest()[:32]


def daily_url():
    key = daily_key()
    host = settings.TELEGRAM_WEBHOOK_HOST
    if not key or not host:
        return ''
    return f'https://{host}{reverse("bot:daily_report", args=[key])}'


def daily_report_view(request, key):
    expected = daily_key()
    if not expected or not hmac.compare_digest(key, expected):
        raise Http404
    from apps.bot.management.commands.daily_report import build_report, send_to_admins
    from apps.bot.models import DailyReportRun

    today = timezone.localdate()
    run, created = DailyReportRun.objects.get_or_create(date=today)
    if not created:
        return HttpResponse('Bugungi hisobot allaqachon yuborilgan.')
    sent = send_to_admins(build_report(today))
    if not sent:
        run.delete()  # hech kimga ketmadi — keyingi urinishda qayta yuborilsin
        return HttpResponse("Hisobotni yuborib bo'lmadi.", status=502)
    return HttpResponse(f'Yuborildi: {sent} ta admin.')
