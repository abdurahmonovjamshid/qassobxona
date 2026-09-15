"""Ruxsat va foydalanuvchi aniqlash. Bitta ADMINS ro'yxati (.env) — veb-saytdagi
kabi rol tizimi yo'q, ro'yxatdagi har bir Telegram ID barcha modullarga to'liq
kirish huquqiga ega bo'ladi (real veb-ilovada ham hozircha shunday: har bir
login qilgan foydalanuvchi hamma narsani qila oladi)."""
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.bot.models import TgUser


def is_admin(telegram_id) -> bool:
    return str(telegram_id) in settings.TELEGRAM_ADMIN_IDS


def get_or_create_tguser(from_user) -> TgUser:
    """`from_user` — telebot `types.User` (message.from_user yoki
    callback_query.from_user). TgUser'ni upsert qiladi; agar bu ID ADMINS
    ro'yxatida bo'lsa va hali bog'langan Django User yo'q bo'lsa, faqat
    servis funksiyalaridagi `created_by=`/`user=` uchun (veb-login emas)
    bitta Django User yaratib bog'laydi."""
    tg_user, _ = TgUser.objects.update_or_create(
        telegram_id=from_user.id,
        defaults={
            'first_name': from_user.first_name or '',
            'last_name': from_user.last_name or '',
            'username': from_user.username or '',
        },
    )
    if is_admin(from_user.id) and tg_user.django_user_id is None:
        User = get_user_model()
        username = f'tg_{from_user.id}'
        django_user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': from_user.first_name or '',
                'last_name': from_user.last_name or '',
                'is_staff': True,
            },
        )
        if django_user.has_usable_password():
            django_user.set_unusable_password()
            django_user.save(update_fields=['password'])
        tg_user.django_user = django_user
        tg_user.save(update_fields=['django_user', 'updated_at'])
    return tg_user
