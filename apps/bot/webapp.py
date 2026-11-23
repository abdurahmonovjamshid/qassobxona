"""Telegram Mini App: bot ichidan saytni ochish.

Mini App ochilganda Telegram sahifaga imzolangan `initData` beradi. Server
uni bot tokeni bilan tekshiradi (https://core.telegram.org/bots/webapps
#validating-data-received-via-the-mini-app), foydalanuvchi ADMINS
ro'yxatida bo'lsa uning bog'langan Django foydalanuvchisi bilan sessiya
ochadi. Shundan keyin saytning oddiy sahifalari Telegram ichida login/parolsiz
ishlaydi.
"""
import hashlib
import hmac
import json
import logging
import time
from types import SimpleNamespace
from urllib.parse import parse_qsl

from django.conf import settings
from django.contrib.auth import login
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.bot.auth import get_or_create_tguser, is_admin

logger = logging.getLogger(__name__)

# initData qancha vaqt amal qiladi (soniya). Telegram har ochilishda yangisini beradi.
INIT_DATA_MAX_AGE = 24 * 60 * 60


def validate_init_data(init_data, bot_token, max_age=INIT_DATA_MAX_AGE, now=None):
    """Imzo to'g'ri va muddati o'tmagan bo'lsa Telegram `user` lug'atini,
    aks holda None qaytaradi."""
    if not init_data or not bot_token:
        return None
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = data.pop('hash', '')
    if not received_hash:
        return None
    check_string = '\n'.join(f'{key}={value}' for key, value in sorted(data.items()))
    secret = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None
    try:
        auth_date = int(data.get('auth_date', '0'))
        user = json.loads(data.get('user') or '{}')
    except (TypeError, ValueError):
        return None
    now = time.time() if now is None else now
    if not auth_date or now - auth_date > max_age:
        return None
    if not isinstance(user, dict) or not user.get('id'):
        return None
    return user


def webapp_url():
    host = settings.TELEGRAM_WEBHOOK_HOST
    return f'https://{host}{reverse("bot:webapp")}' if host else ''


def _safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(
            value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return value
    return reverse('dashboard:index')


@ensure_csrf_cookie
def webapp_page(request):
    """Mini App kirish sahifasi: initData'ni serverga yuboradi va saytga o'tadi."""
    return render(request, 'bot/webapp.html', {
        'app_name': getattr(settings, 'APP_NAME', 'Qassobxona'),
        'next': _safe_next(request, request.GET.get('next')),
    })


@require_POST
def webapp_auth(request):
    tg = validate_init_data(request.POST.get('init_data', ''), settings.TELEGRAM_BOT_TOKEN)
    if tg is None:
        return JsonResponse({'error': "Telegram ma'lumotlari tasdiqlanmadi. Ilovani bot ichidan qayta oching."},
                            status=403)
    if not is_admin(tg['id']):
        return JsonResponse({'error': "Sizga bu ilovadan foydalanishga ruxsat berilmagan."}, status=403)

    tg_user = get_or_create_tguser(SimpleNamespace(
        id=tg['id'],
        first_name=tg.get('first_name', ''),
        last_name=tg.get('last_name', ''),
        username=tg.get('username', ''),
    ))
    user = tg_user.django_user
    if user is None or not user.is_active:
        return JsonResponse({'error': "Foydalanuvchi faol emas."}, status=403)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'next': _safe_next(request, request.POST.get('next'))})


def send_webapp_button(chat_id):
    """Chatga "Ilovani ochish" tugmasini yuboradi va chat menyusi tugmasini
    (yozish maydoni yonidagi) Mini App'ga o'rnatadi."""
    url = webapp_url()
    if not url:
        return
    from telebot import types

    from apps.bot.bot_instance import bot

    try:
        bot.set_chat_menu_button(chat_id=chat_id, menu_button=types.MenuButtonWebApp(
            type='web_app', text='Ilova', web_app=types.WebAppInfo(url)))
    except Exception:
        logger.exception("Chat menyu tugmasini o'rnatib bo'lmadi (chat_id=%s)", chat_id)
    try:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton('📱 Ilovani ochish', web_app=types.WebAppInfo(url)))
        bot.send_message(chat_id, "Grafiklar, hisobotlar va jadvallarni ilovada ko'rish qulayroq:",
                         reply_markup=kb)
    except Exception:
        logger.exception("Ilova tugmasini yuborib bo'lmadi (chat_id=%s)", chat_id)
