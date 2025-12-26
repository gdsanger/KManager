"""
URL configuration for kmanager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
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
from django.contrib import admin
from django.contrib.auth import views as auth_views, logout
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings

class CustomLogoutView(auth_views.LogoutView):
    """Custom logout view that accepts both GET and POST requests and logs out immediately."""
    http_method_names = ['get', 'post']
    
    def get(self, request, *args, **kwargs):
        """Handle GET request by logging out and redirecting."""
        logout(request)
        next_page = self.next_page or settings.LOGOUT_REDIRECT_URL or '/'
        return redirect(next_page)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('vermietung/', include('vermietung.urls')),
    path('', include('core.urls')),
]
