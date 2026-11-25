"""Kunlik hisobot: ADMINS ro'yxatidagi har bir adminga Telegram orqali
bugungi savdo, kassa, qarzlar va kun davomidagi o'chirishlar xulosasi.

PythonAnywhere "Tasks" bo'limida har kuni bir marta ishga tushiriladi:
    cd ~/<loyiha> && <venv>/bin/python manage.py daily_report
`--dry-run` — xabarni yubormasdan ekranga chiqaradi.
"""
import time
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bot.formatters import som
from apps.bot.handlers.dashboard import dashboard_text
from apps.expenses.models import Expense
from apps.payments.models import Payment, active_payments, net_payment_sum
from apps.purchases.models import Purchase
from apps.sales.services.sale_service import get_due_sales


def build_report(today=None):
    today = today or timezone.localdate()
    purchases = Purchase.objects.filter(date=today, status=Purchase.Status.CONFIRMED)
    purchases_total = purchases.aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    customer_in = net_payment_sum(
        active_payments(Payment.objects.filter(date=today, customer__isnull=False)),
        positive_direction=Payment.Direction.IN)
    supplier_out = net_payment_sum(
        active_payments(Payment.objects.filter(date=today, supplier__isnull=False)),
        positive_direction=Payment.Direction.OUT)
    expenses = Expense.objects.filter(date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    due = list(get_due_sales())
    due_total = sum((s.debt_amount for s in due), Decimal('0'))
    todays_logs = AuditLog.objects.filter(created_at__date=today)
    deleted = todays_logs.filter(action=AuditLog.Action.DELETE)

    lines = [
        f"🗓 KUNLIK HISOBOT — {today.strftime('%d.%m.%Y')}",
        '',
        dashboard_text(),
        '',
        '— Bugungi pul oqimi —',
        f'Xaridlar: {som(purchases_total)} ({purchases.count()} ta)',
        f"Mijozlardan tushum: {som(customer_in)}",
        f"Yetkazib beruvchilarga to'lov: {som(supplier_out)}",
        f'Xarajatlar: {som(expenses)}',
        '',
        f"⏰ Muddati kelgan qarzlar: {len(due)} ta, {som(due_total)}",
        f"📝 Bugungi o'zgarishlar: {todays_logs.count()} ta, shundan o'chirilgan: {deleted.count()} ta",
    ]
    for log in deleted[:10]:
        lines.append(f"  • {log.created_at.astimezone(timezone.get_current_timezone()).strftime('%H:%M')} "
                     f"{log.section_label}: {log.object_repr} ({log.user_label})")
    return '\n'.join(lines)


def send_to_admins(text, log=None) -> int:
    """Har bir adminga yuboradi; nechta adminga yetib borganini qaytaradi."""
    sent = 0
    for admin_id in settings.TELEGRAM_ADMIN_IDS:
        try:
            send_with_retry(admin_id, text, attempts=3, delay=2)
            sent += 1
            if log:
                log(f'Yuborildi: {admin_id}')
        except Exception as exc:
            if log:
                log(f"Yuborib bo'lmadi ({admin_id}): {exc}")
    return sent


def send_with_retry(chat_id, text, attempts=4, delay=5):
    from apps.bot.bot_instance import bot

    for attempt in range(1, attempts + 1):
        try:
            for start in range(0, len(text), 4000):  # Telegram xabar chegarasi ~4096
                bot.send_message(chat_id, text[start:start + 4000])
            return True
        except Exception as exc:  # PythonAnywhere proksisi ba'zan 503/429 beradi
            if attempt == attempts:
                raise exc
            time.sleep(delay * attempt)
    return False


class Command(BaseCommand):
    help = "Adminlarga Telegram orqali kunlik hisobot yuboradi."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Yubormasdan ekranga chiqarish')
        parser.add_argument('--url', action='store_true', help='cron-job.org uchun maxfiy havolani chiqarish')

    def handle(self, *args, dry_run=False, url=False, **options):
        if url:
            from apps.bot.daily import daily_url
            self.stdout.write(daily_url() or 'TELEGRAM_BOT_TOKEN yoki HOST sozlanmagan.')
            return
        text = build_report()
        if dry_run:
            self.stdout.write(text)
            return
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_IDS:
            self.stderr.write('TELEGRAM_BOT_TOKEN yoki ADMINS sozlanmagan.')
            return
        send_to_admins(text, log=self.stdout.write)
