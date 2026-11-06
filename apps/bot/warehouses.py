"""Bot oqimlarida "Qaysi ombor?" bosqichi.

Faol ombor bitta bo'lsa savol berilmaydi — o'sha ombor avtomatik tanlanadi.
Bir nechta bo'lsa picker ko'rsatiladi, asosiy ombor ro'yxatda birinchi turadi.
Tanlov `tg_user.data`ga `warehouse_id`/`warehouse_name` sifatida yoziladi va
keyin `next_step(chat_id, tg_user)` chaqiriladi."""
from apps.bot.bot_instance import bot
from apps.bot.pickers import register_pagination, send_picker
from apps.bot.state import register_callback, set_state

_NEXT_STEPS = {}


def active_warehouses():
    from apps.inventory.models import Warehouse
    return [(w.id, w.name) for w in Warehouse.objects.filter(active=True)]


def register_warehouse_picker(prefix, next_step):
    """`prefix` — callback prefiksi (masalan 's_wh'), `next_step` — ombor
    tanlangandan keyingi bosqich."""
    _NEXT_STEPS[prefix] = next_step
    register_pagination(prefix, active_warehouses)

    @register_callback(prefix)
    def _pick(call, tg_user):
        from apps.inventory.models import Warehouse
        warehouse = Warehouse.objects.get(pk=int(call.data.split(':', 1)[1]))
        bot.answer_callback_query(call.id, warehouse.name)
        set_state(tg_user, tg_user.state, warehouse_id=warehouse.id, warehouse_name=warehouse.name)
        next_step(call.message.chat.id, tg_user)

    return _pick


def ask_warehouse(chat_id, tg_user, prefix, title='Qaysi ombor?'):
    items = active_warehouses()
    if len(items) <= 1:
        from apps.inventory.services import inventory_service
        warehouse = inventory_service.resolve_warehouse(None)
        set_state(tg_user, tg_user.state, warehouse_id=warehouse.id, warehouse_name=warehouse.name)
        _NEXT_STEPS[prefix](chat_id, tg_user)
        return
    send_picker(chat_id, prefix, items, title)


def selected_warehouse(tg_user):
    """Oqimda tanlangan ombor (eski, ombor bosqichisiz boshlangan oqimlar
    uchun — asosiy ombor)."""
    from apps.inventory.models import Warehouse
    from apps.inventory.services import inventory_service
    warehouse_id = (tg_user.data or {}).get('warehouse_id')
    if warehouse_id:
        warehouse = Warehouse.objects.filter(pk=warehouse_id).first()
        if warehouse:
            return warehouse
    return inventory_service.resolve_warehouse(None)
