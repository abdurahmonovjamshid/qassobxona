from django import forms

from apps.kassa.models import CashRegister


def cash_register_field(**kwargs):
    """Har bir pulli amaldagi "Kassa" tanlovi. Oldindan Naqd kassa tanlangan."""
    return forms.ModelChoiceField(
        queryset=CashRegister.objects.all(), empty_label=None, label='Kassa', required=False,
        widget=forms.Select(attrs={'class': 'form-select'}), **kwargs,
    )


def setup_cash_register_field(form, name='cash_register'):
    form.fields[name].queryset = CashRegister.objects.all()
    if not form.is_bound and not form.initial.get(name):
        form.initial[name] = CashRegister.get_default().pk


class CashBalanceAdjustmentForm(forms.Form):
    """Kassa balansiga qo'lda naqd pul kiritish (masalan dasturdan foydalanishni
    boshlaganda mavjud naqd qoldiqni belgilash uchun). Faqat superuser
    ishlatishi mumkin — `apps.kassa.views.kassa_add_balance`ga qarang."""

    cash_register = cash_register_field()
    amount = forms.DecimalField(
        max_digits=14, decimal_places=2, label="Summa",
        help_text="Musbat = kassaga kirim, manfiy = kassadan chiqim.",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    date = forms.DateField(
        label="Sana", widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    notes = forms.CharField(
        required=False, label="Izoh",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Masalan: dasturdan foydalanishni boshlashdagi naqd qoldiq"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setup_cash_register_field(self)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount == 0:
            raise forms.ValidationError('Summa nolga teng bolmasligi kerak.')
        return amount
