from django.conf import settings
from django.db import models


class TgUser(models.Model):
    """Botga yozgan Telegram foydalanuvchisi. `django_user` shu Telegram
    foydalanuvchisi uchun avtomatik yaratilgan (yoki bog'langan) Django
    `auth.User` — servis funksiyalaridagi `user=`/`created_by=` argumentlari
    uchun kerak, veb-saytdagi login bilan bog'liq emas.

    `state`/`data` joriy suhbat holatini (FSM) saqlaydi: `state` qaysi
    bosqichda ekanini, `data` shu bosqichgacha to'plangan qiymatlarni
    (masalan sotuv savatchasi) ushlab turadi."""

    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    django_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tg_users',
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    username = models.CharField(max_length=150, blank=True)

    state = models.CharField(max_length=60, blank=True, default='')
    data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Telegram foydalanuvchi'
        verbose_name_plural = 'Telegram foydalanuvchilar'

    def __str__(self):
        return self.username or self.first_name or str(self.telegram_id)

    def reset_state(self):
        self.state = ''
        self.data = {}
        self.save(update_fields=['state', 'data', 'updated_at'])
