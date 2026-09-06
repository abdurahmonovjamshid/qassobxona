from django.db import migrations

CATEGORY_NAMES = {
    'WHOLE': "Butun chorva",
    'BEEF': "Mol go'shti",
    'CHICKEN': "Tovuq go'shti",
    'LAMB': "Qo'y go'shti",
    'FAT': "Yog'",
    'BONE': 'Suyak',
    'WASTE': 'Chiqit',
    'OTHER': 'Boshqa',
}


def migrate_categories(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductCategory = apps.get_model('products', 'ProductCategory')

    codes_in_use = Product.objects.values_list('category', flat=True).distinct()
    category_map = {}
    for code in codes_in_use:
        name = CATEGORY_NAMES.get(code, code)
        category, _ = ProductCategory.objects.get_or_create(code=code, defaults={'name': name})
        category_map[code] = category

    for code, category in category_map.items():
        Product.objects.filter(category=code).update(category_fk=category)


def reverse_categories(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for product in Product.objects.select_related('category_fk').all():
        if product.category_fk_id:
            Product.objects.filter(pk=product.pk).update(category=product.category_fk.code)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_productcategory'),
    ]

    operations = [
        migrations.RunPython(migrate_categories, reverse_categories),
    ]
