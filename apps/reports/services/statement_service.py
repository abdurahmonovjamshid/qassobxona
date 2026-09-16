"""Mijoz/Yetkazib beruvchi uchun akt-sverka (harakatlanuvchi balansli
tranzaksiyalar tarixi) hisoblovchi yordamchi funksiyalar."""
from decimal import Decimal

ZERO = Decimal('0')


def _build(opening_balance, debit_events, credit_events, *, date_from=None, date_to=None):
    """`debit_events`/`credit_events` — {'date', 'op', 'amount', 'category'} lug'atlari ro'yxati.
    Debit balansni oshiradi (masalan sotuv/xarid), credit kamaytiradi (to'lov).
    `date_from`dan oldingi barcha voqealar `opening_balance`ga qo'shib yuboriladi,
    faqat oraliq ichidagilar qatorlar sifatida qaytariladi."""
    all_events = []
    for e in debit_events:
        all_events.append({**e, 'debit': e['amount'], 'credit': ZERO})
    for e in credit_events:
        all_events.append({**e, 'debit': ZERO, 'credit': e['amount']})
    all_events.sort(key=lambda e: e['date'])

    opening = opening_balance
    rows = []
    for e in all_events:
        if date_from and e['date'] < date_from:
            opening += e['debit'] - e['credit']
            continue
        if date_to and e['date'] > date_to:
            continue
        rows.append(e)

    running = opening
    for row in rows:
        running += row['debit'] - row['credit']
        row['balance'] = running

    return {'opening_balance': opening, 'rows': rows, 'closing_balance': running}


def build_customer_statement(customer, *, date_from=None, date_to=None):
    from apps.sales.models import Sale

    sales = customer.sales.filter(status=Sale.Status.CONFIRMED).prefetch_related('items__product')
    payments = customer.payments.all()

    debit_events = [
        {
            'date': s.date, 'op': f'Sotuv {s.sale_number}', 'amount': s.total_amount, 'category': 'Sotuv',
            'sale_id': s.id, 'line_items': list(s.items.all()),
        }
        for s in sales
    ]
    credit_events = [
        {'date': p.date, 'op': "To'lov (sotuv)", 'amount': p.amount, 'category': "To'lov (sotuv)"}
        for p in payments
    ]
    return _build(customer.opening_balance, debit_events, credit_events, date_from=date_from, date_to=date_to)


def build_supplier_statement(supplier, *, date_from=None, date_to=None):
    from apps.purchases.models import Purchase

    purchases = supplier.purchases.filter(status=Purchase.Status.CONFIRMED).prefetch_related('items__product')
    payments = supplier.payments.all()

    debit_events = [
        {
            'date': p.date, 'op': f'Xarid {p.purchase_number}', 'amount': p.total_amount, 'category': 'Xarid',
            'purchase_id': p.id, 'line_items': list(p.items.all()),
        }
        for p in purchases
    ]
    credit_events = [
        {'date': p.date, 'op': "To'lov (xarid)", 'amount': p.amount, 'category': "To'lov (xarid)"}
        for p in payments
    ]
    return _build(supplier.opening_balance, debit_events, credit_events, date_from=date_from, date_to=date_to)


def build_partner_statement(customer, *, date_from=None, date_to=None):
    """Mijoz bir vaqtda yetkazib beruvchi ham bo'lsa (`is_supplier` + `linked_supplier`),
    ikkala tomonning tarixini bitta ro'yxatga birlashtirib, har birini turkumi
    bilan belgilab qaytaradi. Ikkala balans alohida + sof (net) balans hisoblanadi."""
    customer_stmt = build_customer_statement(customer, date_from=date_from, date_to=date_to)
    result = {
        'customer_statement': customer_stmt,
        'supplier_statement': None,
        'rows': [{**r, 'side': 'customer'} for r in customer_stmt['rows']],
        'net_balance': customer_stmt['closing_balance'],
    }
    if customer.is_supplier and customer.linked_supplier_id:
        supplier_stmt = build_supplier_statement(customer.linked_supplier, date_from=date_from, date_to=date_to)
        result['supplier_statement'] = supplier_stmt
        result['rows'] += [{**r, 'side': 'supplier'} for r in supplier_stmt['rows']]
        result['rows'].sort(key=lambda r: r['date'])
        # Sof balans: mijoz bizga qancha qarzdor minus biz yetkazib beruvchiga qancha qarzdormiz.
        result['net_balance'] = customer_stmt['closing_balance'] - supplier_stmt['closing_balance']
    return result


def build_partner_statement_for_supplier(supplier, *, date_from=None, date_to=None):
    """`build_partner_statement`ning Supplier tarafidan kirish nuqtasi: agar shu
    supplier biror Customer bilan bog'langan bo'lsa (Customer.linked_supplier),
    ikkala tomon (sotuv + xarid) birlashtirilib qaytariladi; aks holda faqat
    supplier (xarid) tarafi qaytariladi."""
    from apps.customers.models import Customer

    supplier_stmt = build_supplier_statement(supplier, date_from=date_from, date_to=date_to)
    result = {
        'customer_statement': None,
        'supplier_statement': supplier_stmt,
        'rows': [{**r, 'side': 'supplier'} for r in supplier_stmt['rows']],
        'net_balance': -supplier_stmt['closing_balance'],
    }
    customer = Customer.objects.filter(linked_supplier=supplier, is_supplier=True).first()
    if customer:
        customer_stmt = build_customer_statement(customer, date_from=date_from, date_to=date_to)
        result['customer_statement'] = customer_stmt
        result['rows'] += [{**r, 'side': 'customer'} for r in customer_stmt['rows']]
        result['rows'].sort(key=lambda r: r['date'])
        result['net_balance'] = customer_stmt['closing_balance'] - supplier_stmt['closing_balance']
    return result
