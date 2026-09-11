from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('', views.payment_list, name='list'),
    path('create/', views.payment_create, name='create'),
    path('<int:pk>/cancel/', views.payment_cancel, name='cancel'),
]
