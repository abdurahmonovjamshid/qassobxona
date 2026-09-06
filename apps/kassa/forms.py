from django import forms


class CashBalanceAdjustmentForm(forms.Form):
    """Kassa balansiga qo'lda naqd pul kiritish (masalan dasturdan foydalanishni
    boshlaganda mavjud naqd qoldiqni belgilash uchun). Faqat superuser
    ishlatishi mumkin — `apps.kassa.views.kassa_add_balance`ga qarang."""

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

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount == 0:
            raise forms.ValidationError('Summa nolga teng bolmasligi kerak.')
        return amount
