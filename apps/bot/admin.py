from django.contrib import admin

from apps.bot.models import TgUser


@admin.register(TgUser)
class TgUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'first_name', 'last_name', 'django_user', 'state', 'updated_at')
    search_fields = ('telegram_id', 'username', 'first_name', 'last_name')
    list_filter = ('state',)
    readonly_fields = ('telegram_id', 'django_user', 'data', 'created_at', 'updated_at')
    ordering = ('-updated_at',)
