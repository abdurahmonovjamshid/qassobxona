"""Yagona TeleBot instansiyasi. Boshqa modullar shu yerdan import qiladi va
o'z handlerlarini shunga ro'yxatdan o'tkazadi — hech qanday tarmoq chaqiruvi
(masalan set_webhook) bu yerda BAJARILMAYDI, faqat instansiya yaratiladi."""
import telebot
from django.conf import settings

bot = telebot.TeleBot(settings.TELEGRAM_BOT_TOKEN, threaded=False, parse_mode='HTML')
