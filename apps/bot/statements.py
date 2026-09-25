"""Bot orqali to'liq akt-sverkani .xlsx fayl sifatida yuborish.

Fayl web'dagi `customers/views.py::customer_statement_export` va
`suppliers/views.py::supplier_statement_export` bilan AYNAN bir xil —
bir xil `statement_service` chaqiriladi va bir xil varaqlar tuziladi,
shuning uchun botdan olingan akt saytdan olinganidan farq qilmaydi.

Davr filtri qo'llanilmaydi: bot har doim butun tarixni yuboradi."""
from apps.bot.bot_instance import bot
from apps.common.excel_export import statement_to_bytes
from apps.reports.services import statement_service


def _safe_filename(name: str) -> str:
    """Telegram fayl nomida muammo qilmaydigan holatga keltiradi (kirill/lotin
    harflar qoladi, slash va boshqa belgilar pastki chiziqqa almashadi)."""
    cleaned = ''.join(ch if (ch.isalnum() or ch in ' -_') else '_' for ch in name)
    return cleaned.strip().replace(' ', '_') or 'kontragent'


def _send(chat_id, *, name, sections, summary_lines):
    content = statement_to_bytes(sections=sections)
    caption = '\n'.join([f'📊 Akt-sverka — {name}', *summary_lines])
    bot.send_document(
        chat_id,
        (f'akt-sverka-{_safe_filename(name)}.xlsx', content),
        caption=caption,
    )


def send_customer_statement(chat_id, customer):
    from apps.bot.formatters import som

    statement = statement_service.build_partner_statement(customer)
    sections = [('Mijoz (sotuv)', statement['customer_statement'])]
    summary = [f"Mijoz qarzi: {som(statement['customer_statement']['closing_balance'])}"]
    if statement['supplier_statement']:
        # Bu kontragent bir vaqtda yetkazib beruvchi ham — ikkala taraf ham
        # alohida varaqda ketadi, sof balans esa ularning ayirmasi.
        sections.append(('Yetkazib beruvchi (xarid)', statement['supplier_statement']))
        summary.append(f"Bizning qarzimiz: {som(statement['supplier_statement']['closing_balance'])}")
        summary.append(f"Sof balans: {som(statement['net_balance'])}")
    _send(chat_id, name=customer.name, sections=sections, summary_lines=summary)


def send_supplier_statement(chat_id, supplier):
    from apps.bot.formatters import som

    statement = statement_service.build_partner_statement_for_supplier(supplier)
    sections = [('Yetkazib beruvchi (xarid)', statement['supplier_statement'])]
    summary = [f"Bizning qarzimiz: {som(statement['supplier_statement']['closing_balance'])}"]
    if statement['customer_statement']:
        sections.insert(0, ('Mijoz (sotuv)', statement['customer_statement']))
        summary.append(f"Uning qarzi: {som(statement['customer_statement']['closing_balance'])}")
        summary.append(f"Sof balans: {som(statement['net_balance'])}")
    _send(chat_id, name=supplier.name, sections=sections, summary_lines=summary)
