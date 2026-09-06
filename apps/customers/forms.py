from django import forms

from apps.customers.models import Customer
from apps.suppliers.models import Supplier


class CustomerForm(forms.ModelForm):
    link_existing_supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(active=True), required=False,
        label="Mavjud yetkazib beruvchi bilan bog'lash (ixtiyoriy)",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Bo'sh qoldirilsa va 'Yetkazib beruvchi ham' belgilansa, yangi yetkazib beruvchi avtomatik yaratiladi.",
    )

    class Meta:
        model = Customer
        fields = ['name', 'phone', 'address', 'credit_limit', 'opening_balance', 'is_supplier', 'notes', 'active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'opening_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_supplier': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        customer = super().save(commit=False)
        if customer.is_supplier and not customer.linked_supplier_id:
            existing = self.cleaned_data.get('link_existing_supplier')
            if existing:
                customer.linked_supplier = existing
            else:
                customer.linked_supplier = Supplier.objects.create(
                    name=customer.name, phone=customer.phone, address=customer.address,
                )
        elif not customer.is_supplier:
            customer.linked_supplier = None
        if commit:
            customer.save()
        return customer
