from django import forms
from django.forms import inlineformset_factory

from apps.inventory.models import InventoryCount, InventoryCountItem
from apps.products.models import Product


class InventoryCountForm(forms.ModelForm):
    class Meta:
        model = InventoryCount
        fields = ['date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False


class InventoryCountItemForm(forms.ModelForm):
    class Meta:
        model = InventoryCountItem
        fields = ['product', 'counted_kg', 'counted_pieces']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select', 'data-role': 'count-product'}),
            'counted_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0', 'data-role': 'counted-kg'}),
            'counted_pieces': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0', 'data-role': 'counted-pieces'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(active=True)
        self.fields['counted_pieces'].required = False
        self.fields['counted_pieces'].initial = None

    def clean_counted_pieces(self):
        return self.cleaned_data.get('counted_pieces') or 0


InventoryCountItemFormSet = inlineformset_factory(
    InventoryCount, InventoryCountItem, form=InventoryCountItemForm,
    extra=6, can_delete=True, min_num=1, validate_min=True,
)
