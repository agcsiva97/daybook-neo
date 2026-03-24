from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.DaybookLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('users/', views.users_list, name='users_list'),
    path('users/<str:username>', views.user_info, name='user_info'),
    path('users/<str:username>/edit/', views.edit_user, name='edit_user'),
    path('users/<str:username>/promote-to-admin/', views.promote_to_admin, name='promote_to_admin'),
    path('users/<str:username>/deactivate/', views.deactivate_staff_user, name='deactivate_staff_user'),
    path('users/<str:username>/activate/', views.activate_staff_user, name='activate_staff_user'),
    path('users/create/', views.create_user, name='create_user'),
]
