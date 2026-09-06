from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ButcheringSpecification(models.Model):
    """Bo'laklash usuli (retsept): bitta "father" mahsulotni bo'laklaganda
    odatda qaysi "child" mahsulotlar hosil bolishini belgilaydi. Bitta
    mahsulot bir nechta turli usulda bo'laklanishi mumkin (masalan
    "Standart" va "Tezkor" usullar) — har biri alohida nom bilan saqlanadi."""

    name = models.CharField(max_length=120)
    parent_product = models.ForeignKey(
        'products.Product', on_delete=models.CASCADE, related_name='specifications',
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['parent_product__name', 'name']
        unique_together = ('parent_product', 'name')

    def __str__(self):
        return f'{self.parent_product.name} — {self.name}'


class ButcheringSpecificationItem(models.Model):
    specification = models.ForeignKey(ButcheringSpecification, on_delete=models.CASCADE, related_name='items')
    child_product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT, related_name='specification_sources',
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def clean(self):
        if self.specification_id and self.child_product_id == self.specification.parent_product_id:
            raise ValidationError("Chiqish mahsuloti bo'laklanayotgan mahsulotning o'zi bolmasligi kerak.")

    def __str__(self):
        return f'{self.specification} -> {self.child_product}'


class Butchering(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.PROTECT, related_name='butcherings')
    input_product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='butchering_inputs')
    specification = models.ForeignKey(
        ButcheringSpecification, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='butcherings',
    )
    input_weight = models.DecimalField(max_digits=10, decimal_places=3)
    input_pieces = models.PositiveIntegerField(default=0, help_text="Bo'laklanayotgan dona/bo'lak soni")
    output_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    difference = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    yield_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']

    def clean(self):
        if self.input_weight <= 0:
            raise ValidationError('Input vazn musbat bolishi kerak.')
        if self.output_weight > self.input_weight:
            raise ValidationError('Output inputdan katta bolmasligi kerak.')
        if self.input_product_id:
            from apps.inventory.services import inventory_service
            available = inventory_service.get_stock(self.input_product)
            if self.input_weight > available:
                raise ValidationError(
                    f"Omborda yetarli mahsulot mavjud emas. "
                    f"Mavjud qoldiq: {available} kg ({self.input_product.name})"
                )
            available_pieces = inventory_service.get_stock_pieces(self.input_product)
            if self.input_pieces and self.input_pieces > available_pieces:
                raise ValidationError(
                    f"Omborda yetarli dona/bo'lak mavjud emas. "
                    f"Mavjud qoldiq: {available_pieces} dona ({self.input_product.name})"
                )

    def __str__(self):
        return f'Butchering #{self.pk or "new"}'


class ButcheringOutput(models.Model):
    butchering = models.ForeignKey(Butchering, on_delete=models.CASCADE, related_name='outputs')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='butchering_outputs')
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    pieces = models.PositiveIntegerField(default=0, help_text="Dona/bo'lak soni")
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.quantity is None:
            return
        if self.quantity <= 0:
            raise ValidationError('Output miqdori musbat bolishi kerak.')

    def __str__(self):
        return f'{self.product} - {self.quantity} kg'


class ButcheringExpense(models.Model):
    class ExpenseType(models.TextChoices):
        LABOR = 'LABOR', 'Ishchi kuchi'
        PACKAGING = 'PACKAGING', "Qadoqlash"
        OTHER = 'OTHER', 'Boshqa'

    butchering = models.ForeignKey(Butchering, on_delete=models.CASCADE, related_name='extra_expenses')
    expense_type = models.CharField(max_length=20, choices=ExpenseType.choices, default=ExpenseType.LABOR)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.amount is None:
            return
        if self.amount < 0:
            raise ValidationError('Xarajat manfiy bolmasligi kerak.')

    def __str__(self):
        return f'{self.butchering} - {self.expense_type}'
