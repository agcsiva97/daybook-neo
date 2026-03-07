from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('dashboard/chart-data/', views.dashboard_chart_data, name='dashboard_chart_data'),
    path('dashboard/transaction-pie/', views.transaction_pie_data, name='transaction_pie_data'),
    # Shop CRUD endpoints
    path('shops/', views.shop_list_create, name='shop_list_create'),
    path('shops/<str:pk>/', views.shop_detail, name='shop_detail'),
    path('shops/<str:pk>/ledgers/', views.shop_ledgers, name='shop_ledgers'),
]
