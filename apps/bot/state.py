"""Suhbat holati (FSM) dispatch mexanizmi.

Har bir modul (`handlers/*.py`) o'z ko'p bosqichli oqimining har bir
bosqichini `TgUser.state`dagi noyob satr bilan nomlaydi va shu nomga
`@register_state(...)` orqali funksiyani bog'laydi. Matnli xabarlar shu
bosqich funksiyasiga, inline tugma bosishlari esa `@register_callback(...)`
orqali `call.data`ning ":" gacha bo'lgan prefiksiga bog'langan funksiyaga
yo'naltiriladi (masalan "sale_pick_customer:42" -> prefiks "sale_pick_customer").

Bu PhoneAd-bot'dagi "TgUser.step raqami + bitta katta if/elif" yondashuvining
tartibliroq varianti: bir nechta modul (8+ ta oqim) uchun kengaytirish osonroq.
"""
STATE_HANDLERS = {}
CALLBACK_HANDLERS = {}


def register_state(state_name):
    def decorator(fn):
        STATE_HANDLERS[state_name] = fn
        return fn
    return decorator


def register_callback(prefix):
    def decorator(fn):
        CALLBACK_HANDLERS[prefix] = fn
        return fn
    return decorator


def dispatch_text(message, tg_user) -> bool:
    handler = STATE_HANDLERS.get(tg_user.state)
    if handler is None:
        return False
    handler(message, tg_user)
    return True


def dispatch_callback(call, tg_user) -> bool:
    prefix = call.data.split(':', 1)[0]
    handler = CALLBACK_HANDLERS.get(prefix)
    if handler is None:
        return False
    handler(call, tg_user)
    return True


def set_state(tg_user, state, **data_updates):
    """`tg_user.state`ni yangilaydi va `data_updates`ni joriy `tg_user.data`ga
    qo'shib (merge) saqlaydi — har bir bosqichda butun scratch datani qayta
    yozib yubormaslik uchun."""
    data = dict(tg_user.data or {})
    data.update(data_updates)
    tg_user.state = state
    tg_user.data = data
    tg_user.save(update_fields=['state', 'data', 'updated_at'])


def clear_state(tg_user):
    tg_user.reset_state()
