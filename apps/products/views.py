from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.inventory.services import inventory_service
from apps.products.forms import ProductCategoryForm, ProductForm
from apps.products.models import Product, ProductCategory


@login_required
def product_list(request):
    products = Product.objects.select_related('category').all()
    q = request.GET.get('q')
    category_id = request.GET.get('category')
    if q:
        products = products.filter(name__icontains=q)
    if category_id:
        products = products.filter(category_id=category_id)

    rows = [
        {'product': p, 'stock': inventory_service.get_stock(p)}
        for p in products
    ]
    return render(request, 'products/list.html', {
        'rows': rows,
        'categories': ProductCategory.objects.all(),
    })


@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"{product.name} qo'shildi.")
            return redirect('products:detail', pk=product.pk)
    else:
        form = ProductForm()
    return render(request, 'products/form.html', {'form': form, 'title': 'Yangi mahsulot'})


@login_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"{product.name} yangilandi.")
            return redirect('products:detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)
    return render(request, 'products/form.html', {'form': form, 'title': product.name, 'product': product})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    stock = inventory_service.get_stock(product)
    return render(request, 'products/detail.html', {
        'product': product,
        'stock': stock,
        'stock_pieces': inventory_service.get_stock_pieces(product),
        'specifications': product.specifications.filter(active=True).prefetch_related('items__child_product'),
    })


@login_required
def category_list(request):
    categories = ProductCategory.objects.all()
    return render(request, 'products/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    if request.method == 'POST':
        form = ProductCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Kategoriya qo'shildi.")
            return redirect('products:category_list')
    else:
        form = ProductCategoryForm()
    return render(request, 'products/category_form.html', {'form': form})
