from django.urls import path

from . import views

app_name = 'entries'

urlpatterns = [
    path('', views.home, name='home'),
    path('add-entries/', views.add_entries, name='add_entries'),
    path('transfer/', views.transfer, name='transfer'),
    path('loan/', views.loan, name='loan'),
    path('loans/', views.loans, name='loans'),
    path('loans/<str:pk>/edit/', views.edit_loan, name='edit_loan'),
    path('loans/<str:pk>/delete/', views.delete_loan, name='delete_loan'),
    path('loans/<str:pk>/history/', views.loan_history, name='loan_history'),
    path('transactions/', views.transactions, name='transactions'),
    path('transactions/export/csv/', views.export_transactions_csv, name='export_transactions_csv'),
    path('transactions/export/excel/', views.export_transactions_excel, name='export_transactions_excel'),
    path('transactions/<str:pk>/edit/', views.edit_transaction, name='edit_transaction'),
    path('transactions/<str:pk>/delete/', views.delete_transaction, name='delete_transaction'),
    path('transactions/<str:pk>/history/', views.transaction_history, name='transaction_history'),
    path('denominations/', views.denominations, name='denominations'),
    path('denomination/', views.denomination, name='denomination'),
    path('denomination/users/', views.get_users_for_denomination, name='get_users_for_denomination'),
    path('denomination/view/<str:key>/', views.view_denomination, name='view_denomination'),
    path('denomination/edit/<str:key>/', views.edit_denomination, name='edit_denomination'),
    path('denomination/delete/<str:key>/', views.delete_denomination, name='delete_denomination'),
    path('report/', views.report, name='report'),
    path('report/export/csv/', views.export_report_csv, name='export_report_csv'),
    path('report/export/excel/', views.export_report_excel, name='export_report_excel'),
    path('about/', views.about, name='about'),

]
