# manager/urls.py
from django.urls import path
from . import views
from entries import views as entry_views

app_name = 'manager'

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('balance-sheet/', views.balance_sheet, name='balance_sheet'),
    path('shops/', views.shops_list, name='shops_list'),
    path('sync-history/', views.sync_history, name='sync_history'),
    path('export/<int:export_id>/details/', views.export_details, name='export_details'),
    path('import/<int:import_id>/details/', views.import_details, name='import_details'),
    path('import-transactions/', views.import_transactions, name='import_transactions'),
    path('shops/import/', views.import_shop, name='import_shop'),
    path('shops/add/', views.add_shop, name='add_shop'),
    path('shops/<str:pk>/', views.shop_info, name='shop_info'),
    path('shops/<str:pk>/export/', views.export_shop, name='export_shop'),
    path('shops/<str:pk>/export-transactions/', views.export_transactions, name='export_transactions'),
    path('shops/<str:pk>/balance_sheet', views.type_balance_sheet, name='shop_balance_sheet'),
    path('shops/<str:pk>/balance_sheet/<str:type_pk>/acc_type/', views.account_balance_sheet, name='type_balance_sheet'),
    path('shops/<str:pk>/sync_acc_types', views.sync_grp_typ, name='shop_sync_grp_typ'),
    path('shops/<str:pk>/add_account', views.add_account, name='add-account'),
    path('shops/<str:pk>/edit/', views.edit_shop, name='edit_shop'),
    path('shops/<str:pk>/delete/', views.delete_shop, name='delete_shop'),
    path('shops/<str:shop_pk>/add-ledger/', views.add_shop_ledger, name='add_shop_ledger'),
    path('ledger/<str:pk>/', views.ledger_info, name='ledger_info'),
    path('ledger/<str:pk>/edit/', views.edit_ledger, name='edit_ledger'),
    path('ledger/<str:pk>/delete/', views.delete_ledger, name='delete_ledger'),
    path('accounts/move-transactions/', views.move_transactions, name='move_transactions'),
    path('accounts/update-tally/', views.update_tally_transactions, name='update_tally_transactions'),
    path('accounts/<str:pk>/', views.account_info, name='account_info'),
    path('accounts/<str:pk>/edit/', views.account_edit, name='account_edit'),
    path('accounts/<str:pk>/delete/', views.delete_account, name='delete_account'),
    path('configuration/', views.configurations, name='configurations'),
    path('activity-logs/', views.activity_logs, name='activity_logs'),
]