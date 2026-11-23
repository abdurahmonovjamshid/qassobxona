"""Biznes modellaridagi har bir yaratish / o'zgartirish / o'chirishni
`AuditLog`ga yozadi. Jurnal xatosi hech qachon asosiy saqlashni buzmasligi
kerak — shuning uchun hammasi try/except ichida.

Eslatma: `queryset.update()` va `bulk_create()` signal yubormaydi, ular
jurnalga tushmaydi (loyihada asosiy hujjatlar `.save()` orqali saqlanadi)."""
import datetime
import logging
from decimal import Decimal

from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save

from apps.audit.context import current_actor

logger = logging.getLogger(__name__)

TRACKED_APPS = {
    'products', 'sales', 'purchases', 'butchering', 'inventory', 'customers',
    'suppliers', 'payments', 'expenses', 'kassa',
}
# Hujjatlardan avtomatik hosil bo'ladigan yozuvlar — ular hujjatning o'zida ko'rinadi.
SKIPPED_MODELS = {'inventory.stockmovement'}
IGNORED_FIELDS = {'id', 'created_at', 'updated_at'}


def _tracked(sender):
    meta = sender._meta
    return meta.app_label in TRACKED_APPS and meta.label_lower not in SKIPPED_MODELS


def _skip_instance(instance):
    # Kassadagi hujjatga bog'liq (to'lov, xarajat...) harakatlar hujjatning o'zida
    # yoziladi; qo'lda kiritilgan kassa harakatlari esa jurnalga tushadi.
    return instance._meta.label_lower == 'kassa.cashtransaction' and bool(getattr(instance, 'reference', ''))


def _fields(model):
    return [f for f in model._meta.concrete_fields if f.name not in IGNORED_FIELDS]


def _raw(instance):
    return {f.name: f.value_from_object(instance) for f in _fields(type(instance))}


def _fmt(value):
    if value is None or value == '':
        return ''
    if isinstance(value, bool):
        return 'Ha' if value else "Yo'q"
    if isinstance(value, Decimal):
        value = value.normalize()
        return format(value, 'f')
    if isinstance(value, datetime.datetime):
        return value.strftime('%d.%m.%Y %H:%M')
    if isinstance(value, datetime.date):
        return value.strftime('%d.%m.%Y')
    return str(value)[:200]


def _display(field, value):
    if value is None or value == '':
        return ''
    if field.is_relation:
        related = field.related_model._base_manager.filter(pk=value).first()
        return str(related)[:200] if related is not None else f'#{value}'
    if field.choices:
        return str(dict(field.flatchoices).get(value, value))
    return _fmt(value)


def _diff(model, old, new):
    changes = []
    for field in _fields(model):
        before, after = old.get(field.name), new.get(field.name)
        if before == after:
            continue
        changes.append([str(field.verbose_name).capitalize(), _display(field, before), _display(field, after)])
    return changes


def _write(instance, action, changes=None):
    from django.contrib.contenttypes.models import ContentType

    from apps.audit.models import AuditLog

    user, source = current_actor()
    try:
        repr_ = str(instance)
    except Exception:
        repr_ = f'#{instance.pk}'
    # Savepoint: jurnal xatosi tashqi tranzaksiyani buzmasin.
    with transaction.atomic():
        AuditLog.objects.create(
            user_id=user.pk if user else None,
            source=source,
            action=action,
            content_type=ContentType.objects.get_for_model(type(instance)),
            object_id=str(instance.pk),
            object_repr=repr_[:255],
            changes=changes or [],
        )


def on_pre_save(sender, instance, raw=False, **kwargs):
    if raw or not _tracked(sender) or instance.pk is None:
        return
    try:
        old = sender._base_manager.filter(pk=instance.pk).first()
        instance._audit_old = _raw(old) if old is not None else None
    except Exception:
        logger.exception('Audit: eski qiymatlarni o\'qib bo\'lmadi')


def on_post_save(sender, instance, created, raw=False, **kwargs):
    if raw or not _tracked(sender) or _skip_instance(instance):
        return
    try:
        old = getattr(instance, '_audit_old', None)
        instance._audit_old = None
        if created or old is None:
            _write(instance, 'create')
            return
        changes = _diff(sender, old, _raw(instance))
        if changes:
            _write(instance, 'update', changes)
    except Exception:
        logger.exception('Audit: saqlashni yozib bo\'lmadi')


def on_post_delete(sender, instance, **kwargs):
    if not _tracked(sender) or _skip_instance(instance):
        return
    try:
        _write(instance, 'delete')
    except Exception:
        logger.exception('Audit: o\'chirishni yozib bo\'lmadi')


def connect():
    for model in apps.get_models():
        if _tracked(model):
            pre_save.connect(on_pre_save, sender=model, dispatch_uid=f'audit_pre_{model._meta.label_lower}')
            post_save.connect(on_post_save, sender=model, dispatch_uid=f'audit_post_{model._meta.label_lower}')
            post_delete.connect(on_post_delete, sender=model, dispatch_uid=f'audit_del_{model._meta.label_lower}')
