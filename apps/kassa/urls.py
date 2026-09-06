from django.urls import path

from . import views

app_name = 'kassa'

urlpatterns = [
    path('', views.kassa_detail, name='detail'),
]
