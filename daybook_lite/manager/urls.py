# manager/urls.py
from django.urls import path
from . import views
from entries import views as entry_views

app_name = 'manager'

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('shops/', views.shops_list, name='shops_list'),
    path('shops/add/', views.add_shop, name='add_shop'),
    path('shops/<str:pk>/', views.shop_info, name='shop_info'),
    path('shops/<str:pk>/edit/', views.edit_shop, name='edit_shop'),
    path('shops/<str:pk>/delete/', views.delete_shop, name='delete_shop'),
    path('shops/<str:shop_pk>/add-ledger/', views.add_shop_ledger, name='add_shop_ledger'),
    path('ledger/<str:pk>/', views.ledger_info, name='ledger_info'),
    path('ledger/<str:pk>/edit/', views.edit_ledger, name='edit_ledger'),
    path('ledger/<str:pk>/delete/', views.delete_ledger, name='delete_ledger'),
    path('configuration/', views.configurations, name='configurations'),
    path('activity-logs/', views.activity_logs, name='activity_logs'),
]