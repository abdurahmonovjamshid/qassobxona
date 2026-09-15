import logging
import traceback

import telebot
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt

from apps.bot.auth import get_or_create_tguser, is_admin
from apps.bot.bot_instance import bot

logger = logging.getLogger(__name__)


@csrf_exempt
def telegram_webhook(request, token):
    if token != settings.TELEGRAM_BOT_TOKEN:
        raise Http404
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        update = telebot.types.Update.de_json(request.body.decode('utf-8'))
        from_user = None
        if update.message is not None:
            from_user = update.message.from_user
        elif update.callback_query is not None:
            from_user = update.callback_query.from_user

        if from_user is not None:
            get_or_create_tguser(from_user)
            if is_admin(from_user.id):
                bot.process_new_updates([update])
    except Exception:
        logger.exception('Telegram webhook update ni qayta ishlashda xatolik')
        traceback.print_exc()

    # Telegram faqat 200 javobni kutadi; xatolik bo'lsa ham qayta urinishlarni
    # (retry storm) oldini olish uchun doim "ok" qaytariladi.
    return HttpResponse('ok')


def _auto_set_webhook():
    """PhoneAd-bot'dagi kabi: bu modul import qilinganda (ya'ni server har
    reload bo'lganda — gunicorn/WSGI worker boot, `manage.py runserver`
    va h.k.) webhook avtomatik qayta o'rnatiladi. TELEGRAM_BOT_TOKEN yoki
    HOST sozlanmagan bo'lsa (masalan lokal muhitda .env to'liq emas)
    jimgina o'tkazib yuboriladi; tarmoq xatosi ham butun ilovani
    qulatmasligi uchun tutib olinadi."""
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_WEBHOOK_HOST):
        return
    try:
        url = f'https://{settings.TELEGRAM_WEBHOOK_HOST}/bot/{settings.TELEGRAM_BOT_TOKEN}/webhook/'
        bot.set_webhook(url=url)
        logger.info("Telegram webhook o'rnatildi: %s", url)
    except Exception:
        logger.exception("Telegram webhook'ni avtomatik o'rnatishda xatolik")


_auto_set_webhook()
