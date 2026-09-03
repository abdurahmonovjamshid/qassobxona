from django.urls import path

from . import views

app_name = 'purchases'

urlpatterns = [
    path('', views.purchase_list, name='list'),
    path('create/', views.purchase_create, name='create'),
    path('<int:pk>/', views.purchase_detail, name='detail'),
    path('<int:pk>/cancel/', views.purchase_cancel, name='cancel'),
]
