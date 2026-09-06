from django.urls import path

from . import views

app_name = 'customers'

urlpatterns = [
    path('', views.customer_list, name='list'),
    path('create/', views.customer_create, name='create'),
    path('<int:pk>/', views.customer_detail, name='detail'),
    path('<int:pk>/edit/', views.customer_update, name='update'),
    path('<int:pk>/statement/', views.customer_statement, name='statement'),
    path('<int:pk>/statement/export/', views.customer_statement_export, name='statement_export'),
]
