"""
URL configuration for daybook_lite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import views as app_views

from accounts import views

# Custom error handlers
handler404 = 'entries.views.custom_404_view'
handler403 = 'entries.views.custom_403_view'

urlpatterns = [
    path('', app_views.home, name='daybookhome'), 
    path('daybook/', include('entries.urls')),
    path('api/', include('api.urls')),
    path('admin/', admin.site.urls),
    path('manager/', include('accounts.urls')),path('usersettings/', views.user_settings, name='user_settings'),
    path('usersettings/', views.user_settings, name='user_settings'),
    path('usersettings/edit/', views.edit_profile, name='edit_profile'),
    path('usersettings/password/', views.change_password, name='change_password'),
    path('manager/', include('manager.urls')), 
]

# Static files are now served by WhiteNoise middleware
# No need for manual static() configuration
