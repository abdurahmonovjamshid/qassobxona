"""Joriy harakatni kim qilayotganini (foydalanuvchi va manba) saqlaydi.

Sayt so'rovlarida `AuditMiddleware`, Telegram botda webhook view
`audit_actor(...)` orqali o'rnatadi. Hech biri bo'lmasa (masalan
management buyruq) — manba "Tizim", foydalanuvchi yo'q."""
import contextvars
from contextlib import contextmanager

_actor = contextvars.ContextVar('audit_actor', default=None)


@contextmanager
def audit_actor(user, source):
    """`user` — User yoki uni qaytaradigan funksiya (so'rovdagi lazy user uchun)."""
    token = _actor.set((user, source))
    try:
        yield
    finally:
        _actor.reset(token)


def current_actor():
    value = _actor.get()
    if not value:
        return None, 'system'
    user, source = value
    if callable(user):
        user = user()
    if user is None or not getattr(user, 'is_authenticated', False):
        return None, source
    return user, source
