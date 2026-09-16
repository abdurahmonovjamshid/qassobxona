"""Yangi xarid/sotuv/bo'laklash TASDIQLANGANDA `TELEGRAM_ADMIN_IDS`dagi barcha
adminlarga xabar yuboradi (xarid/sotuv uchun — PDF nakladnoy ilova qilib).

Chaqiruvchi joy (`purchase_service.confirm_purchase` va h.k.) bu funksiyalarni
`transaction.on_commit(...)` ichida chaqiradi — DB tranzaksiyasi muvaffaqiyatli
commit bo'lgandan KEYIN ishga tushadi, shunda Telegram tarmoq xatosi hech
qachon biznes operatsiyasini bekor qilmaydi. Shu sababli bu yerdagi har bir
funksiya o'z ichida try/except bilan himoyalangan — bitta adminga yuborish
muvaffaqiyatsiz bo'lsa (bloklangan bot, noto'g'ri ID) ham qolganlariga
yuborish davom etadi va operatsiyaning o'zi allaqachon saqlangan bo'ladi."""
import contextvars
import io
import logging
from contextlib import contextmanager

from django.conf import settings

from apps.bot.bot_instance import bot
from apps.bot.formatters import kg
from apps.bot.formatters import pieces as pieces_fmt
from apps.bot.formatters import som

logger = logging.getLogger(__name__)

_suppressed = contextvars.ContextVar('admin_notify_suppressed', default=False)


@contextmanager
def suppressed():
    """Demo/seed skriptlari uchun — shu blok ichida (va uning
    `transaction.on_commit` orqali keyinroq ishga tushadigan qismlarida ham,
    chunki ContextVar shu context'ni meros qilib oladi) hech qanday admin
    xabari yuborilmaydi. Masalan `seed_demo_data` o'nlab soxta xarid/sotuv
    yaratganda haqiqiy adminlarga spam ketmasligi uchun shu bilan o'raladi."""
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)


def _actor_name(user) -> str:
    if not user:
        return "Noma'lum"
    full = (user.get_full_name() or '').strip()
    return full or user.username


def _broadcast(text, *, document: bytes | None = None, document_name: str | None = None):
    if _suppressed.get():
        return
    for admin_id in settings.TELEGRAM_ADMIN_IDS:
        try:
            chat_id = int(admin_id)
        except ValueError:
            continue
        try:
            bot.send_message(chat_id, text)
            if document is not None:
                bot.send_document(chat_id, io.BytesIO(document), visible_file_name=document_name)
        except Exception:
            logger.exception("Adminga (telegram_id=%s) xabar yuborib bo'lmadi.", admin_id)


def notify_new_purchase(purchase, *, user=None):
    from apps.common.pdf_documents import build_purchase_pdf

    items = list(purchase.items.select_related('product').all())
    lines = [
        f'🐄 <b>Yangi xarid tasdiqlandi</b> — {purchase.purchase_number}',
        f"Sana: {purchase.date.strftime('%d.%m.%Y')}",
        f'Yetkazib beruvchi: {purchase.supplier.name}',
        '',
        'Mahsulotlar:',
    ]
    for item in items:
        lines.append(
            f'• {item.product.name} — {kg(item.net_weight)}, {pieces_fmt(item.pieces)} '
            f'× {som(item.price_per_kg)} = {som(item.total)}'
        )
    lines += [
        '',
        f'Jami: {som(purchase.total_amount)}',
        f"To'langan: {som(purchase.paid_amount)}",
        f'Qarz: {som(purchase.debt_amount)}',
        f'Tasdiqladi: {_actor_name(user)}',
    ]
    try:
        pdf_bytes = build_purchase_pdf(purchase)
    except Exception:
        logger.exception('Xarid nakladnoy PDF yaratib bolmadi: %s', purchase.purchase_number)
        pdf_bytes = None
    _broadcast('\n'.join(lines), document=pdf_bytes, document_name=f'{purchase.purchase_number}.pdf')


def notify_new_sale(sale, *, user=None):
    from apps.common.pdf_documents import build_sale_pdf

    items = list(sale.items.select_related('product').all())
    lines = [
        f'💰 <b>Yangi sotuv tasdiqlandi</b> — {sale.sale_number}',
        f"Sana: {sale.date.strftime('%d.%m.%Y')}",
        f'Mijoz: {sale.customer.name}',
        '',
        'Mahsulotlar:',
    ]
    for item in items:
        lines.append(
            f'• {item.product.name} — {kg(item.quantity)}, {pieces_fmt(item.pieces)} '
            f'× {som(item.price)} = {som(item.total)}'
        )
    lines += [
        '',
        f'Jami: {som(sale.total_amount)}',
        f"To'langan: {som(sale.paid_amount)}",
        f'Qarz: {som(sale.debt_amount)}',
        f'Tasdiqladi: {_actor_name(user)}',
    ]
    try:
        pdf_bytes = build_sale_pdf(sale)
    except Exception:
        logger.exception('Sotuv nakladnoy PDF yaratib bolmadi: %s', sale.sale_number)
        pdf_bytes = None
    _broadcast('\n'.join(lines), document=pdf_bytes, document_name=f'{sale.sale_number}.pdf')


def notify_new_butchering(butchering, *, user=None):
    outputs = list(butchering.outputs.select_related('product').all())
    lines = [
        f"🔪 <b>Bo'laklash tasdiqlandi</b> — #{butchering.pk}",
        f"Sana: {butchering.date.strftime('%d.%m.%Y')}",
        f'Kirim: {butchering.input_product.name} — {kg(butchering.input_weight)}, '
        f'{pieces_fmt(butchering.input_pieces)}',
        '',
        'Chiqishlar:',
    ]
    for output in outputs:
        lines.append(f'• {output.product.name} — {kg(output.quantity)}, {pieces_fmt(output.pieces)}')
    lines += [
        '',
        f'Chiqim: {butchering.yield_percentage}%',
        f'Tasdiqladi: {_actor_name(user)}',
    ]
    _broadcast('\n'.join(lines))
