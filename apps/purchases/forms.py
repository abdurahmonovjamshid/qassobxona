from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.payments.models import Payment
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseExpense, PurchaseItem
from apps.suppliers.models import Supplier


class PurchaseForm(forms.ModelForm):
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
        model = Purchase
        fields = ['supplier', 'date', 'notes']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(active=True)
        self.fields['notes'].required = False


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ['product', 'net_weight', 'pieces', 'price_per_kg']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select', 'data-role': 'item-product'}),
            'net_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0', 'data-role': 'item-net-weight'}),
            'pieces': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0', 'data-role': 'item-pieces'}),
            'price_per_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'data-role': 'item-price'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(active=True)
        self.fields['pieces'].required = False
        self.fields['pieces'].initial = None

    def clean_pieces(self):
        return self.cleaned_data.get('pieces') or 0


PurchaseItemFormSet = inlineformset_factory(
    Purchase, PurchaseItem, form=PurchaseItemForm,
    extra=3, can_delete=True, min_num=1, validate_min=True,
)


class PurchaseExpenseForm(forms.ModelForm):
    class Meta:
        model = PurchaseExpense
        fields = ['expense_type', 'amount', 'notes']
        widgets = {
            'expense_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'data-role': 'expense-amount'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False


PurchaseExpenseFormSet = inlineformset_factory(
    Purchase, PurchaseExpense, form=PurchaseExpenseForm,
    extra=2, can_delete=True,
)
