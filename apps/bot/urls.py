from django.urls import path

from apps.bot.views import telegram_webhook

app_name = 'bot'

urlpatterns = [
    path('<str:token>/webhook/', telegram_webhook, name='webhook'),
]
