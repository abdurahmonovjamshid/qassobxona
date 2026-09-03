from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='index'),
    path('sales/', views.sales_report_view, name='sales'),
    path('purchases/', views.purchase_report_view, name='purchases'),
    path('inventory/', views.inventory_report_view, name='inventory'),
    path('debtor/', views.debtor_report_view, name='debtor'),
    path('creditor/', views.creditor_report_view, name='creditor'),
    path('profit/', views.profit_report_view, name='profit'),
]
