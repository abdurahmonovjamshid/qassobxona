"""Akt-sverka (statement) natijasini .xlsx faylga aylantirish uchun umumiy
yordamchi. `apps/reports/services/statement_service.py` qaytargan
dict'lardan (`opening_balance`, `rows`, `closing_balance`) foydalanadi."""
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from django.http import HttpResponse
from django.utils import timezone


def _item_kg(item) -> Decimal:
    # Xarid qatorida vazn `net_weight`, sotuv qatorida esa `quantity`.
    kg = item.net_weight if hasattr(item, 'net_weight') else item.quantity
    return kg or Decimal('0')


def _item_price(item) -> Decimal:
    # Xarid qatorida 1 kg narxi `price_per_kg`, sotuv qatorida esa `price`.
    return item.price_per_kg if hasattr(item, 'price_per_kg') else item.price


def _line_items_prices(line_items):
    """1 kg narxi ustuni: hamma qatorda narx bir xil bo'lsa — son, aks holda
    "Mahsulotlar" ustunidagi qatorlar tartibida har birining narxi."""
    prices = [_item_price(item) for item in line_items]
    if not prices:
        return None
    if len(set(prices)) == 1:
        return float(prices[0])
    return '\n'.join(f'{price.normalize():f}' for price in prices)


def _line_items_summary(line_items):
    """Hujjat qatorlarini "Mahsulot — 12.5 kg (3 dona)" ko'rinishidagi matnga
    va jami kg'ga aylantiradi."""
    parts = []
    total = Decimal('0')
    for item in line_items:
        kg = _item_kg(item)
        total += kg
        text = f'{item.product.name} — {kg.normalize():f} kg'
        if item.pieces:
            text += f' ({item.pieces} dona)'
        parts.append(text)
    return '\n'.join(parts), total


def _write_sheet(ws, title, statement):
    ws.append([title])
    ws['A1'].font = Font(bold=True, size=14)
    ws.append([])
    ws.append(["Boshlang'ich saldo", float(statement['opening_balance'])])
    ws.append([])

    header = ['Sana', 'Operatsiya', 'Turkum', 'Mahsulotlar', 'Jami kg', '1 kg narxi', 'Kirim (+)', 'Chiqim (-)', 'Balans', 'Izoh']
    ws.append(header)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    for row in statement['rows']:
        line_items = row.get('line_items') or []
        products, total_kg = _line_items_summary(line_items)
        ws.append([
            row['date'].strftime('%d.%m.%Y'),
            row['op'],
            row.get('category', ''),
            products,
            float(total_kg) if total_kg else None,
            _line_items_prices(line_items),
            float(row['debit']),
            float(row['credit']),
            float(row['balance']),
            row.get('notes') or '',
        ])
        for column in (4, 6):
            ws.cell(row=ws.max_row, column=column).alignment = Alignment(wrap_text=True, vertical='top')

    ws.append([])
    ws.append(['Yakuniy saldo', '', '', '', '', '', '', '', float(statement['closing_balance'])])
    ws[f'A{ws.max_row}'].font = Font(bold=True)

    for column_cells in ws.columns:
        length = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=10)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 12), 40)


def _build_statement_workbook(sections):
    """`sections` — [(sheet_title, statement_dict), ...]. Kamida bitta bo'lishi kerak."""
    wb = Workbook()
    for i, (title, statement) in enumerate(sections):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = title[:31]
        _write_sheet(ws, title, statement)
    return wb


def statement_to_response(*, filename, sections):
    """Brauzerga yuklab beriladigan .xlsx javobi."""
    wb = _build_statement_workbook(sections)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


def statement_to_bytes(*, sections) -> bytes:
    """Xuddi shu .xlsx, lekin HTTP javobi emas, xotiradagi baytlar sifatida —
    Telegram bot `send_document` bilan yuborishi uchun."""
    buffer = BytesIO()
    _build_statement_workbook(sections).save(buffer)
    return buffer.getvalue()


def table_to_response(*, filename_prefix, headers, rows, sheet_title='Sheet1'):
    """Oddiy jadval (headers + rows) ni .xlsx faylga aylantiradi.

    Fayl nomiga yuklab olingan sana va soat qo'shiladi
    (masalan `mijozlar_2026-09-11_14-30-05.xlsx`), shu bilan qaysi vaqtda
    olingan hisobot ekani faylning o'zidan ko'rinib turadi.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for row in rows:
        ws.append(row)

    for column_cells in ws.columns:
        length = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=10)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 12), 40)

    timestamp = timezone.localtime().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f'{filename_prefix}_{timestamp}.xlsx'

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response
