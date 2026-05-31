from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    # Configuration endpoints
    path('config/session-timeout/', views.get_session_timeout, name='get_session_timeout'),
    # Dashboard endpoints
    path('dashboard/chart-data/', views.dashboard_chart_data, name='dashboard_chart_data'),
    path('dashboard/transaction-pie/', views.transaction_pie_data, name='transaction_pie_data'),
    path('balance-sheet/networth/', views.networth_chart_data, name='networth_chart_data'),
    path('dashboard/bt-ledger-monthly/', views.bt_ledger_monthly_chart_data, name='bt_ledger_monthly_chart_data'),
    path('dashboard/loan-gauge/', views.loan_gauge_data, name='loan_gauge_data'),
    # Shop CRUD endpoints
    path('shops/', views.shop_list_create, name='shop_list_create'),
    path('transactions/', views.get_transactions, name='transactions'),
    path('shops/<str:pk>/', views.shop_detail, name='shop_detail'),
    path('shops/<str:pk>/ledgers/', views.shop_ledger_list_create, name='shop_ledgers'),
    path('shops/<str:pk>/accounts/', views.shop_account_list, name='shop_accounts'),
    path('shops/<str:pk>/types/', views.shop_type_list, name='shop_types'),
    path('shops/<str:pk>/transactions/', views.get_shop_transactions, name='shop_transactions'),
]
