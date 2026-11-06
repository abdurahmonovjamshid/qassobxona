from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.common.date_filters import get_date_range
from apps.payments.forms import PaymentForm
from apps.payments.models import Payment
from apps.payments.services import payment_service


@login_required
def payment_list(request):
    payments = Payment.objects.select_related('customer', 'supplier', 'sale', 'purchase', 'cash_register').all()
    payment_type = request.GET.get('payment_type')
    direction = request.GET.get('direction')
    date_from, date_to = get_date_range(request)
    if payment_type:
        payments = payments.filter(payment_type=payment_type)
    if direction:
        payments = payments.filter(direction=direction)
    if date_from:
        payments = payments.filter(date__gte=date_from)
    if date_to:
        payments = payments.filter(date__lte=date_to)

    return render(request, 'payments/list.html', {
        'payments': payments[:200],
        'payment_types': Payment.PaymentType.choices,
        'directions': Payment.Direction.choices,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
def payment_create(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                payment_service.create_payment(
                    amount=data['amount'], cash_register=data.get('cash_register'), date=data['date'],
                    direction=data['direction'],
                    customer=data.get('customer'), supplier=data.get('supplier'),
                    sale=data.get('sale'), purchase=data.get('purchase'),
                    notes=data.get('notes', ''), user=request.user,
                )
                messages.success(request, "To'lov muvaffaqiyatli qo'shildi.")
                if data.get('sale'):
                    return redirect('sales:detail', pk=data['sale'].pk)
                if data.get('purchase'):
                    return redirect('purchases:detail', pk=data['purchase'].pk)
                if data.get('customer'):
                    return redirect('customers:detail', pk=data['customer'].pk)
                if data.get('supplier'):
                    return redirect('suppliers:detail', pk=data['supplier'].pk)
                return redirect('payments:list')
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
    else:
        initial = {'date': timezone.localdate()}
        for key in ('customer', 'supplier', 'sale', 'purchase'):
            value = request.GET.get(key)
            if value:
                initial[key] = value
        # Yo'nalish havolada ko'rsatilsa (masalan "Undan pul olish" tugmasi)
        # o'shani, aks holda tomonga qarab odatdagisini oldindan tanlaymiz.
        direction = request.GET.get('direction')
        if direction in Payment.Direction.values:
            initial['direction'] = direction
        elif request.GET.get('supplier') or request.GET.get('purchase'):
            initial['direction'] = Payment.Direction.OUT
        else:
            initial['direction'] = Payment.Direction.IN
        form = PaymentForm(initial=initial)

    return render(request, 'payments/form.html', {'form': form})


@login_required
def payment_cancel(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        sale_id, purchase_id = payment.sale_id, payment.purchase_id
        customer_id, supplier_id = payment.customer_id, payment.supplier_id
        try:
            payment_service.delete_payment(payment, user=request.user)
            messages.success(request, "To'lov bekor qilindi.")
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('payments:list')
        if sale_id:
            return redirect('sales:detail', pk=sale_id)
        if purchase_id:
            return redirect('purchases:detail', pk=purchase_id)
        if customer_id:
            return redirect('customers:detail', pk=customer_id)
        if supplier_id:
            return redirect('suppliers:detail', pk=supplier_id)
    return redirect('payments:list')
