from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseExpense
from apps.suppliers.models import Supplier


class PurchaseForm(forms.ModelForm):
    paid_amount = forms.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=Decimal('0'),
        initial=Decimal('0'), label="Boshlang'ich to'lov",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
    )

    class Meta:
        model = Purchase
        fields = ['supplier', 'product', 'date', 'animal_type', 'gross_weight', 'net_weight', 'price_per_kg', 'notes']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select d-none', 'data-role': 'product-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'animal_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mol, Qoy...'}),
            'gross_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'net_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0', 'data-role': 'net-weight'}),
            'price_per_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'data-role': 'price-per-kg'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(active=True)
        self.fields['product'].queryset = Product.objects.filter(active=True)
        self.fields['notes'].required = False


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
