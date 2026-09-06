from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.customers.models import Customer
from apps.payments.models import Payment
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem


class SaleForm(forms.ModelForm):
    paid_amount = forms.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=Decimal('0'),
        initial=Decimal('0'), label="Boshlang'ich to'lov",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
    )
    payment_type = forms.ChoiceField(
        choices=Payment.PaymentType.choices, required=False, initial=Payment.PaymentType.CASH,
        label="To'lov turi", widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Sale
        fields = ['customer', 'date']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select d-none', 'data-role': 'customer-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(active=True)


class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'pieces', 'price', 'discount']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select d-none', 'data-role': 'product-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0', 'data-role': 'qty'}),
            'pieces': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0', 'data-role': 'pieces'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'data-role': 'price'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'data-role': 'discount'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(active=True)
        self.fields['discount'].required = False
        self.fields['pieces'].required = False
        # Model field default=0 makes Django auto-set initial=0, which breaks
        # has_changed() detection for blank extra formset rows. Reset it.
        self.fields['discount'].initial = None
        self.fields['pieces'].initial = None

    def clean_discount(self):
        return self.cleaned_data.get('discount') or Decimal('0')

    def clean_pieces(self):
        return self.cleaned_data.get('pieces') or 0


SaleItemFormSet = inlineformset_factory(
    Sale, SaleItem, form=SaleItemForm,
    extra=3, can_delete=True, min_num=1, validate_min=True,
)
