"""Kunlik hisobot maxfiy havolasi (cron-job.org uchun)."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.bot.daily import daily_key, daily_url
from apps.bot.models import DailyReportRun


@override_settings(TELEGRAM_BOT_TOKEN='123:TEST', TELEGRAM_ADMIN_IDS=['1', '2'], TELEGRAM_WEBHOOK_HOST='example.com')
class DailyReportUrlTests(TestCase):
    def url(self, key=None):
        return reverse('bot:daily_report', args=[key or daily_key()])

    def test_url_contains_key(self):
        self.assertEqual(daily_url(), f'https://example.com{self.url()}')

    def test_wrong_key_404(self):
        self.assertEqual(self.client.get(self.url('0' * 32)).status_code, 404)

    @patch('apps.bot.management.commands.daily_report.send_with_retry')
    def test_sends_once_per_day(self, send):
        first = self.client.get(self.url())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(send.call_count, 2)
        second = self.client.get(self.url())
        self.assertContains(second, 'allaqachon')
        self.assertEqual(send.call_count, 2)
        self.assertEqual(DailyReportRun.objects.count(), 1)

    @patch('apps.bot.management.commands.daily_report.send_with_retry', side_effect=RuntimeError('503'))
    def test_failed_send_can_retry(self, send):
        self.assertEqual(self.client.get(self.url()).status_code, 502)
        self.assertFalse(DailyReportRun.objects.exists())
