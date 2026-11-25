from django.urls import path

from apps.bot.daily import daily_report_view
from apps.bot.views import telegram_webhook
from apps.bot.webapp import webapp_auth, webapp_page

app_name = 'bot'

urlpatterns = [
    path('daily/<str:key>/', daily_report_view, name='daily_report'),
    path('app/', webapp_page, name='webapp'),
    path('app/auth/', webapp_auth, name='webapp_auth'),
    path('<str:token>/webhook/', telegram_webhook, name='webhook'),
]
