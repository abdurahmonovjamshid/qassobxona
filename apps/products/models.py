from django.db import models


class ProductCategory(models.Model):
    name = models.CharField(max_length=80)
    code = models.CharField(max_length=20, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Product categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    class Unit(models.TextChoices):
        KG = 'kg', 'kg'

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.PROTECT, related_name='products')
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.KG)
    sale_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'
