from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.customers.forms import CustomerForm
from apps.customers.models import Customer
from apps.sales.models import Sale


@login_required
def customer_list(request):
    customers = Customer.objects.all()
    q = request.GET.get('q')
    if q:
        customers = customers.filter(name__icontains=q)

    rows = []
    for customer in customers:
        total_sales = customer.sales.filter(status=Sale.Status.CONFIRMED).aggregate(
            s=Sum('total_amount'))['s'] or Decimal('0')
        total_debt = customer.sales.filter(status=Sale.Status.CONFIRMED).aggregate(
            s=Sum('debt_amount'))['s'] or Decimal('0')
        rows.append({'customer': customer, 'total_sales': total_sales, 'debt': total_debt})

    return render(request, 'customers/list.html', {'rows': rows})


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
    return render(request, 'customers/form.html', {'form': form})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    sales = customer.sales.exclude(status=Sale.Status.CANCELLED)
    payments = customer.payments.all()

    total_sales = sales.filter(status=Sale.Status.CONFIRMED).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    total_payments = payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    debt = sales.filter(status=Sale.Status.CONFIRMED).aggregate(s=Sum('debt_amount'))['s'] or Decimal('0')

    history = []
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
