"""Har bir modul import qilinganda o'z @bot.message_handler /
@bot.callback_query_handler / @register_state("...") registratsiyalarini
ishga tushiradi. Shu sababli bu fayl ularning barchasini import qiladi —
boshqa hech narsa qilmaydi."""
from apps.bot.handlers import (  # noqa: F401
    butchering,
    common,
    customers,
    dashboard,
    expenses,
    inventory,
    kassa,
    payments,
    purchases,
    reports,
    sales,
    suppliers,
)
