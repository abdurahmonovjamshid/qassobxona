from django.urls import path

from . import views

app_name = 'suppliers'

urlpatterns = [
    path('', views.supplier_list, name='list'),
    path('export/', views.supplier_list_export, name='list_export'),
    path('create/', views.supplier_create, name='create'),
    path('<int:pk>/', views.supplier_detail, name='detail'),
    path('<int:pk>/edit/', views.supplier_update, name='update'),
    path('<int:pk>/statement/', views.supplier_statement, name='statement'),
    path('<int:pk>/statement/export/', views.supplier_statement_export, name='statement_export'),
]
