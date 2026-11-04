from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_list, name='list'),
    path('export/', views.inventory_export, name='export'),
    path('import/', views.inventory_import, name='import'),
    path('counts/', views.inventory_count_list, name='count_list'),
    path('counts/create/', views.inventory_count_create, name='count_create'),
    path('counts/<int:pk>/', views.inventory_count_detail, name='count_detail'),
    path('transfers/', views.transfer_list, name='transfer_list'),
    path('transfers/create/', views.transfer_create, name='transfer_create'),
    path('transfers/<int:pk>/', views.transfer_detail, name='transfer_detail'),
    path('transfers/<int:pk>/cancel/', views.transfer_cancel, name='transfer_cancel'),
]
