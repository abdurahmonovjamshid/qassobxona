from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.bot.bot_instance import bot


class Command(BaseCommand):
    help = (
        "Telegram bot webhook'ini settings.TELEGRAM_WEBHOOK_HOST (.env HOST) "
        "manziliga o'rnatadi. Faqat bitta marta (yoki HOST o'zgarganda) qo'lda "
        "ishga tushiriladi — import vaqtida avtomatik chaqirilmaydi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--remove', action='store_true',
            help="Webhook'ni o'rnatish o'rniga o'chiradi (bot.remove_webhook()).",
        )

    def handle(self, *args, **options):
        if options['remove']:
            bot.remove_webhook()
            self.stdout.write(self.style.SUCCESS("Webhook o'chirildi."))
            return

        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError('TELEGRAM_BOT_TOKEN .env faylida topilmadi.')
        if not settings.TELEGRAM_WEBHOOK_HOST:
            raise CommandError('HOST .env faylida topilmadi.')

        url = f'https://{settings.TELEGRAM_WEBHOOK_HOST}/bot/{settings.TELEGRAM_BOT_TOKEN}/webhook/'
        bot.remove_webhook()
        bot.set_webhook(url=url)
        self.stdout.write(self.style.SUCCESS(f"Webhook o'rnatildi: {url}"))
