"""reportlab asosida oddiy "nakladnoy" PDF hujjatlari — xarid/sotuv
tasdiqlanganda Telegram orqali adminlarga yuborish uchun (`apps.bot.admin_notify`).
Faqat matn/jadval, tashqi shrift/logotip shart emas — reportlab core
(Helvetica) shrifti standart lotin harflari va apostrofni to'liq qamrab oladi."""
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def som(value) -> str:
    value = Decimal(value or 0).quantize(Decimal('1'))
    sign = '-' if value < 0 else ''
    grouped = f'{abs(int(value)):,}'.replace(',', ' ')
    return f"{sign}{grouped} so'm"


_styles = getSampleStyleSheet()
_title_style = ParagraphStyle('DocTitle', parent=_styles['Heading1'], alignment=TA_CENTER, fontSize=16)

_TABLE_HEADER_STYLE = [
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
]


def _info_table(rows):
    t = Table(rows, colWidths=[45 * mm, None])
    t.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    return t


def _signature_block():
    return _info_table([
        ["Topshirdi (F.I.Sh, imzo): _____________________", ''],
        ["Qabul qildi (F.I.Sh, imzo): _____________________", ''],
    ])


def build_purchase_pdf(purchase) -> bytes:
    """Xarid uchun nakladnoy: yetkazib beruvchi, mahsulotlar ro'yxati, jami/
    to'langan/qarz va imzo joyi."""
    items = list(purchase.items.select_related('product').all())

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    elements = [
        Paragraph('NAKLADNOY — Xarid', _title_style),
        Spacer(1, 6 * mm),
        _info_table([
            ['№:', purchase.purchase_number],
            ['Sana:', purchase.date.strftime('%d.%m.%Y')],
            ['Yetkazib beruvchi:', purchase.supplier.name],
        ]),
        Spacer(1, 6 * mm),
    ]

    data = [['#', 'Mahsulot', 'Netto (kg)', 'Dona', 'Narx/kg', 'Summa']]
    for i, item in enumerate(items, 1):
        data.append([
            str(i), item.product.name, f'{item.net_weight:.3f}', str(item.pieces),
            som(item.price_per_kg), som(item.total),
        ])
    table = Table(data, colWidths=[10 * mm, 55 * mm, 25 * mm, 15 * mm, 30 * mm, 30 * mm], repeatRows=1)
    table.setStyle(TableStyle(_TABLE_HEADER_STYLE))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(_info_table([
        ['Jami:', som(purchase.total_amount)],
        ["To'langan:", som(purchase.paid_amount)],
        ['Qarz:', som(purchase.debt_amount)],
    ]))
    elements.append(Spacer(1, 20 * mm))
    elements.append(_signature_block())

    doc.build(elements)
    return buf.getvalue()


def build_sale_pdf(sale) -> bytes:
    """Sotuv uchun nakladnoy: mijoz, mahsulotlar ro'yxati (chegirma bilan),
    jami/to'langan/qarz va imzo joyi."""
    items = list(sale.items.select_related('product').all())

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    elements = [
        Paragraph('NAKLADNOY — Sotuv', _title_style),
        Spacer(1, 6 * mm),
        _info_table([
            ['№:', sale.sale_number],
            ['Sana:', sale.date.strftime('%d.%m.%Y')],
            ['Mijoz:', sale.customer.name],
        ]),
        Spacer(1, 6 * mm),
    ]

    data = [['#', 'Mahsulot', 'Miqdor (kg)', 'Dona', 'Narx', 'Chegirma', 'Summa']]
    for i, item in enumerate(items, 1):
        data.append([
            str(i), item.product.name, f'{item.quantity:.3f}', str(item.pieces),
            som(item.price), som(item.discount), som(item.total),
        ])
    table = Table(
        data, colWidths=[8 * mm, 45 * mm, 22 * mm, 13 * mm, 25 * mm, 25 * mm, 27 * mm], repeatRows=1,
    )
    table.setStyle(TableStyle(_TABLE_HEADER_STYLE))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(_info_table([
        ['Jami:', som(sale.total_amount)],
        ["To'langan:", som(sale.paid_amount)],
        ['Qarz:', som(sale.debt_amount)],
    ]))
    elements.append(Spacer(1, 20 * mm))
    elements.append(_signature_block())

    doc.build(elements)
    return buf.getvalue()
