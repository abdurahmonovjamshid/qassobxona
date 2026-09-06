from django.urls import path

from . import views

app_name = 'butchering'

urlpatterns = [
    path('', views.butchering_list, name='list'),
    path('create/', views.butchering_create, name='create'),
    path('specifications/', views.specification_list, name='specification_list'),
    path('specifications/create/', views.specification_create, name='specification_create'),
    path('<int:pk>/', views.butchering_detail, name='detail'),
    path('<int:pk>/cancel/', views.butchering_cancel, name='cancel'),
]
