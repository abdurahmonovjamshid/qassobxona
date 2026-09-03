from django import forms

from apps.customers.models import Customer
from apps.payments.models import Payment
from apps.purchases.models import Purchase
from apps.sales.models import Sale
from apps.suppliers.models import Supplier


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_type', 'amount', 'date', 'customer', 'supplier', 'sale', 'purchase', 'notes']
        widgets = {
            'payment_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'sale': forms.Select(attrs={'class': 'form-select'}),
            'purchase': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(active=True)
        self.fields['customer'].required = False
        self.fields['supplier'].queryset = Supplier.objects.filter(active=True)
        self.fields['supplier'].required = False
        self.fields['sale'].queryset = Sale.objects.filter(status=Sale.Status.CONFIRMED)
        self.fields['sale'].required = False
        self.fields['purchase'].queryset = Purchase.objects.filter(status=Purchase.Status.CONFIRMED)
        self.fields['purchase'].required = False
        self.fields['notes'].required = False

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get('customer')
        supplier = cleaned.get('supplier')
        if customer and supplier:
            raise forms.ValidationError("To'lov bir vaqtda mijoz va supplierga tegishli bo'lmasin.")
        if not customer and not supplier:
            raise forms.ValidationError("To'lov mijoz yoki supplierga bog'lanishi kerak.")
        return cleaned
