from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_list, name='list'),
    path('counts/', views.inventory_count_list, name='count_list'),
    path('counts/create/', views.inventory_count_create, name='count_create'),
    path('counts/<int:pk>/', views.inventory_count_detail, name='count_detail'),
]
