from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.audit.context import audit_actor
from apps.audit.models import AuditLog
from apps.customers.models import Customer


class AuditLogTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('boss', password='x-test-pass-1')

    def test_create_update_delete_logged(self):
        with audit_actor(self.user, 'web'):
            customer = Customer.objects.create(name='Ali')
            customer.name = 'Ali aka'
            customer.save()
            customer.save()  # o'zgarishsiz saqlash jurnalga tushmaydi
            customer.delete()

        logs = list(AuditLog.objects.order_by('id'))
        self.assertEqual([log.action for log in logs], ['create', 'update', 'delete'])
        self.assertTrue(all(log.user_id == self.user.pk and log.source == 'web' for log in logs))
        label, old, new = logs[1].changes[0]
        self.assertEqual((old, new), ('Ali', 'Ali aka'))

    def test_without_actor_is_system(self):
        Customer.objects.create(name='Vali')
        log = AuditLog.objects.get()
        self.assertIsNone(log.user_id)
        self.assertEqual(log.source, 'system')

    def test_web_request_records_user(self):
        self.client.force_login(self.user)
        with audit_actor(None, 'system'):
            pass
        self.client.get(reverse('audit:list'))  # faqat o'qish — yozuv yo'q
        self.assertFalse(AuditLog.objects.exists())

    def test_list_page(self):
        with audit_actor(self.user, 'bot'):
            Customer.objects.create(name='Hasan')
        self.client.force_login(self.user)
        response = self.client.get(reverse('audit:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hasan')
        self.assertContains(response, 'Telegram bot')

    def test_list_requires_login(self):
        self.assertEqual(self.client.get(reverse('audit:list')).status_code, 302)


class DailyReportTests(TestCase):
    def test_dry_run(self):
        with audit_actor(None, 'web'):
            Customer.objects.create(name='Olim').delete()
        out = StringIO()
        call_command('daily_report', '--dry-run', stdout=out)
        text = out.getvalue()
        self.assertIn('KUNLIK HISOBOT', text)
        self.assertIn("o'chirilgan: 1 ta", text)
        self.assertIn('Olim', text)
