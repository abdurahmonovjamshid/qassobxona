from django.apps import AppConfig


class BotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.bot'
    verbose_name = 'Telegram bot'

    def ready(self):
        # Handlerlarni bir marta, Django ilovasi yuklanganda ro'yxatdan
        # o'tkazadi (tarmoq chaqiruvi yo'q — faqat @bot.message_handler /
        # @register_state dekoratorlari ishga tushadi).
        from apps.bot import handlers  # noqa: F401
