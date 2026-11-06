from django import forms
from django.forms import inlineformset_factory

from apps.inventory.models import (
    InventoryCount, InventoryCountItem, StockTransfer, StockTransferItem, Warehouse,
)
from apps.products.models import Product


def setup_warehouse_field(form, name='warehouse'):
    """Hujjat formasidagi "Ombor" maydoni: faqat faol omborlar, yangi
    hujjatda asosiy ombor tanlangan holda. Bo'sh kelsa (masalan eski
    mijoz/API) servislar asosiy omborni ishlatadi."""
    field = form.fields[name]
    field.queryset = Warehouse.objects.filter(active=True)
    field.required = False
    field.empty_label = None
    field.label = 'Ombor'
    if not form.instance.pk or not getattr(form.instance, f'{name}_id'):
        form.initial.setdefault(name, Warehouse.get_default().pk)


WAREHOUSE_WIDGET = forms.Select(attrs={'class': 'form-select', 'data-role': 'warehouse-select'})


class InventoryCountForm(forms.ModelForm):
    class Meta:
        model = InventoryCount
        fields = ['date', 'warehouse', 'notes']
        widgets = {
            'warehouse': WAREHOUSE_WIDGET,
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False
        setup_warehouse_field(self)


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


class InventoryImportForm(forms.Form):
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(active=True), empty_label=None, label='Ombor', required=False,
        help_text="Bo'sh bo'lsa asosiy ombor",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    file = forms.FileField(
        label='Excel fayl (.xlsx)',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx'}),
    )


class StockTransferForm(forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = ['date', 'from_warehouse', 'to_warehouse', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'from_warehouse': forms.Select(attrs={'class': 'form-select', 'data-role': 'warehouse-select'}),
            'to_warehouse': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setup_warehouse_field(self, 'from_warehouse')
        setup_warehouse_field(self, 'to_warehouse')
        self.fields['from_warehouse'].label = 'Qaysi ombordan'
        self.fields['to_warehouse'].label = 'Qaysi omborga'
        other = Warehouse.objects.filter(active=True, is_default=False).first()
        if other and not self.is_bound:
            self.initial['to_warehouse'] = other.pk
        self.fields['notes'].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('from_warehouse') and cleaned.get('from_warehouse') == cleaned.get('to_warehouse'):
            raise forms.ValidationError("Qaysi ombordan va qaysi omborga — har xil bo'lishi kerak.")
        return cleaned


class StockTransferItemForm(forms.ModelForm):
    class Meta:
        model = StockTransferItem
        fields = ['product', 'quantity', 'pieces']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select', 'data-role': 'transfer-product'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'pieces': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(active=True)
        self.fields['quantity'].required = False
        self.fields['quantity'].initial = None
        self.fields['pieces'].required = False
        self.fields['pieces'].initial = None

    def clean_quantity(self):
        return self.cleaned_data.get('quantity') or 0

    def clean_pieces(self):
        return self.cleaned_data.get('pieces') or 0

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('product') and not cleaned.get('quantity') and not cleaned.get('pieces'):
            raise forms.ValidationError("Kg yoki dona sonini kiriting.")
        return cleaned


StockTransferItemFormSet = inlineformset_factory(
    StockTransfer, StockTransferItem, form=StockTransferItemForm,
    extra=5, can_delete=True, min_num=1, validate_min=True,
)
