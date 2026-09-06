from django import forms
from django.forms import inlineformset_factory

from apps.butchering.models import (
    Butchering, ButcheringExpense, ButcheringOutput,
    ButcheringSpecification, ButcheringSpecificationItem,
)
from apps.products.models import Product
from apps.purchases.models import Purchase


class ButcheringForm(forms.ModelForm):
    class Meta:
        model = Butchering
        fields = ['purchase', 'input_product', 'specification', 'input_weight', 'date', 'notes']
        widgets = {
            'purchase': forms.Select(attrs={'class': 'form-select', 'data-role': 'purchase-select'}),
            'input_product': forms.Select(attrs={'class': 'form-select', 'data-role': 'input-product-select'}),
            'specification': forms.Select(attrs={'class': 'form-select', 'data-role': 'specification-select'}),
            'input_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0', 'data-role': 'input-weight'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['purchase'].queryset = Purchase.objects.filter(status=Purchase.Status.CONFIRMED)
        # Bo'laklashga faqat kamida bitta faol spetsifikatsiyaga ega
        # mahsulotlar chaqirilishi mumkin.
        self.fields['input_product'].queryset = Product.objects.filter(
            active=True, specifications__active=True,
        ).distinct()
        self.fields['specification'].queryset = ButcheringSpecification.objects.filter(active=True)
        self.fields['specification'].required = False
        self.fields['notes'].required = False


class ButcheringOutputForm(forms.ModelForm):
    class Meta:
        model = ButcheringOutput
        fields = ['product', 'quantity', 'pieces']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select', 'data-role': 'output-product'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0', 'data-role': 'output-qty'}),
            'pieces': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0', 'data-role': 'output-pieces'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(active=True)
        self.fields['pieces'].required = False
        self.fields['pieces'].initial = None

    def clean_pieces(self):
        return self.cleaned_data.get('pieces') or 0


ButcheringOutputFormSet = inlineformset_factory(
    Butchering, ButcheringOutput, form=ButcheringOutputForm,
    extra=6, can_delete=True, min_num=1, validate_min=True,
)


class ButcheringExpenseForm(forms.ModelForm):
    class Meta:
        model = ButcheringExpense
        fields = ['expense_type', 'amount', 'notes']
        widgets = {
            'expense_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'data-role': 'butchering-expense-amount'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False


ButcheringExpenseFormSet = inlineformset_factory(
    Butchering, ButcheringExpense, form=ButcheringExpenseForm,
    extra=2, can_delete=True,
)


class ButcheringSpecificationForm(forms.ModelForm):
    class Meta:
        model = ButcheringSpecification
        fields = ['parent_product', 'name', 'active']
        widgets = {
            'parent_product': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Masalan: Standart usul"}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent_product'].queryset = Product.objects.filter(active=True)


class ButcheringSpecificationItemForm(forms.ModelForm):
    class Meta:
        model = ButcheringSpecificationItem
        fields = ['child_product', 'order']
        widgets = {
            'child_product': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['child_product'].queryset = Product.objects.filter(active=True)
        self.fields['order'].required = False
        self.fields['order'].initial = None

    def clean_order(self):
        return self.cleaned_data.get('order') or 0


ButcheringSpecificationItemFormSet = inlineformset_factory(
    ButcheringSpecification, ButcheringSpecificationItem, form=ButcheringSpecificationItemForm,
    extra=4, can_delete=True, min_num=1, validate_min=True,
)
