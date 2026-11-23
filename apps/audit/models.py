from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


def section_label(content_type):
    model = content_type.model_class()
    return str(model._meta.verbose_name).capitalize() if model else content_type.model


class AuditLog(models.Model):
    """Kim, qachon, qayerdan (sayt / bot / admin) nimani yaratdi, o'zgartirdi
    yoki o'chirdi. Yozuvlar avtomatik — `apps/audit/signals.py`."""

    class Action(models.TextChoices):
        CREATE = 'create', 'Yaratildi'
        UPDATE = 'update', "O'zgartirildi"
        DELETE = 'delete', "O'chirildi"

    class Source(models.TextChoices):
        WEB = 'web', 'Sayt'
        BOT = 'bot', 'Telegram bot'
        ADMIN = 'admin', 'Admin panel'
        SYSTEM = 'system', 'Tizim'

    created_at = models.DateTimeField('Vaqt', auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Foydalanuvchi', on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='+')
    source = models.CharField('Manba', max_length=10, choices=Source.choices, default=Source.SYSTEM)
    action = models.CharField('Harakat', max_length=10, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, verbose_name="Bo'lim", on_delete=models.CASCADE, related_name='+')
    object_id = models.CharField(max_length=64)
    object_repr = models.CharField('Hujjat', max_length=255)
    # [[maydon nomi, eski qiymat, yangi qiymat], ...]
    changes = models.JSONField("O'zgarishlar", default=list, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Harakat'
        verbose_name_plural = 'Harakatlar jurnali'

    def __str__(self):
        return f'{self.get_action_display()}: {self.object_repr}'

    @property
    def section_label(self):
        return section_label(self.content_type)

    @property
    def user_label(self):
        if self.user is None:
            return self.get_source_display()
        return self.user.get_full_name() or self.user.username
