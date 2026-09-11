from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from apps.common.date_filters import get_date_range
from apps.common.excel_export import statement_to_response, table_to_response
from apps.customers.forms import CustomerForm
from apps.customers.models import Customer
from apps.reports.services import statement_service
from apps.sales.models import Sale


def _filtered_customers(request):
    customers = Customer.objects.all()
    q = request.GET.get('q')
    if q:
        customers = customers.filter(name__icontains=q)
    return customers


@login_required
def customer_list(request):
    customers = _filtered_customers(request)

    rows = [{'customer': customer, 'debt': customer.get_total_debt()} for customer in customers]

    return render(request, 'customers/list.html', {'rows': rows})


@login_required
def customer_list_export(request):
    customers = _filtered_customers(request)
    headers = ['Ism', 'Telefon', 'Qarz', 'Holat']
    rows = [
        [customer.name, customer.phone, float(customer.get_total_debt()), 'Faol' if customer.active else 'Nofaol']
        for customer in customers
    ]
    return table_to_response(filename_prefix='mijozlar', headers=headers, rows=rows, sheet_title='Mijozlar')


@login_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f"{customer.name} qo'shildi.")
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerForm()
    return render(request, 'customers/form.html', {'form': form, 'title': 'Yangi mijoz'})


@login_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f"{customer.name} yangilandi.")
            return redirect('customers:detail', pk=customer.pk)
    else:
        initial = {'link_existing_supplier': customer.linked_supplier_id}
        form = CustomerForm(instance=customer, initial=initial)
    return render(request, 'customers/form.html', {'form': form, 'title': customer.name, 'customer': customer})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    sales = customer.sales.exclude(status=Sale.Status.CANCELLED)
    payments = customer.payments.all()

    total_sales = customer.get_total_sales()
    total_payments = customer.get_total_payments()
    debt = customer.get_total_debt()

    history = []
    if customer.opening_balance:
        history.append({
            'date': customer.created_at.date(), 'op': "Boshlang'ich qarz",
            'amount': customer.opening_balance, 'kind': 'opening',
        })
    for sale in sales:
        history.append({'date': sale.date, 'op': f'Sotuv {sale.sale_number}', 'amount': sale.total_amount, 'kind': 'sale'})
    for payment in payments:
        history.append({'date': payment.date, 'op': "To'lov", 'amount': payment.amount, 'kind': 'payment'})
    history.sort(key=lambda h: h['date'])

    return render(request, 'customers/detail.html', {
        'customer': customer,
        'total_sales': total_sales,
        'total_payments': total_payments,
        'debt': debt,
        'history': history,
        'sales': sales,
    })


@login_required
def customer_statement(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    date_from, date_to = get_date_range(request)
    statement = statement_service.build_partner_statement(
        customer, date_from=parse_date(date_from) if date_from else None,
        date_to=parse_date(date_to) if date_to else None,
    )
    return render(request, 'customers/statement.html', {
        'customer': customer,
        'statement': statement,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
def customer_statement_export(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    date_from, date_to = get_date_range(request)
    statement = statement_service.build_partner_statement(
        customer, date_from=parse_date(date_from) if date_from else None,
        date_to=parse_date(date_to) if date_to else None,
    )
    sections = [('Mijoz (sotuv)', statement['customer_statement'])]
    if statement['supplier_statement']:
        sections.append(('Yetkazib beruvchi (xarid)', statement['supplier_statement']))
    return statement_to_response(filename=f'akt-sverka-{customer.name}.xlsx', sections=sections)
