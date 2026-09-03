from django import forms
from django.forms import inlineformset_factory

from apps.butchering.models import Butchering, ButcheringOutput
from apps.products.models import Product
from apps.purchases.models import Purchase


class ButcheringForm(forms.ModelForm):
    class Meta:
        model = Butchering
        fields = ['purchase', 'input_product', 'input_weight', 'date', 'notes']
        widgets = {
            'purchase': forms.Select(attrs={'class': 'form-select', 'data-role': 'purchase-select'}),
            'input_product': forms.Select(attrs={'class': 'form-select', 'data-role': 'input-product-select'}),
            'input_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0', 'data-role': 'input-weight'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['purchase'].queryset = Purchase.objects.filter(status=Purchase.Status.CONFIRMED)
        self.fields['input_product'].queryset = Product.objects.filter(active=True)
        self.fields['notes'].required = False


class ButcheringOutputForm(forms.ModelForm):
    class Meta:
        model = ButcheringOutput
        fields = ['product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select', 'data-role': 'output-product'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0', 'data-role': 'output-qty'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(active=True)


ButcheringOutputFormSet = inlineformset_factory(
    Butchering, ButcheringOutput, form=ButcheringOutputForm,
    extra=6, can_delete=True, min_num=1, validate_min=True,
)
