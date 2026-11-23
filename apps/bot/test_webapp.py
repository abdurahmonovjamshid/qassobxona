"""Telegram Mini App: initData imzosini tekshirish va sessiya ochish."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.bot.models import TgUser
from apps.bot.webapp import validate_init_data

TOKEN = '123456:TEST-TOKEN'


def make_init_data(user, token=TOKEN, auth_date=None):
    fields = {
        'auth_date': str(int(time.time()) if auth_date is None else auth_date),
        'query_id': 'AAE1',
        'user': json.dumps(user, separators=(',', ':')),
    }
    check = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class ValidateInitDataTests(TestCase):
    def test_valid(self):
        user = validate_init_data(make_init_data({'id': 42, 'first_name': 'Ali'}), TOKEN)
        self.assertEqual(user['id'], 42)

    def test_wrong_token(self):
        self.assertIsNone(validate_init_data(make_init_data({'id': 42}, token='1:OTHER'), TOKEN))

    def test_tampered(self):
        data = make_init_data({'id': 42}).replace('42', '43')
        self.assertIsNone(validate_init_data(data, TOKEN))

    def test_expired(self):
        old = int(time.time()) - 3 * 24 * 60 * 60
        self.assertIsNone(validate_init_data(make_init_data({'id': 42}, auth_date=old), TOKEN))

    def test_empty(self):
        self.assertIsNone(validate_init_data('', TOKEN))
        self.assertIsNone(validate_init_data(make_init_data({'id': 42}), ''))


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_ADMIN_IDS=['42'])
class WebAppAuthTests(TestCase):
    def post(self, init_data, next_url=''):
        return self.client.post(reverse('bot:webapp_auth'), {'init_data': init_data, 'next': next_url})

    def test_page_renders(self):
        response = self.client.get(reverse('bot:webapp'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'telegram-web-app.js')

    def test_admin_logs_in(self):
        response = self.post(make_init_data({'id': 42, 'first_name': 'Ali'}), '/kassa/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['next'], '/kassa/')
        tg_user = TgUser.objects.get(telegram_id=42)
        self.assertEqual(int(self.client.session['_auth_user_id']), tg_user.django_user_id)
        self.assertEqual(self.client.get(reverse('dashboard:index')).status_code, 200)

    def test_external_next_ignored(self):
        response = self.post(make_init_data({'id': 42}), 'https://evil.example/')
        self.assertEqual(response.json()['next'], reverse('dashboard:index'))

    def test_non_admin_rejected(self):
        response = self.post(make_init_data({'id': 7}))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_bad_signature_rejected(self):
        response = self.post(make_init_data({'id': 42}, token='1:OTHER'))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)
