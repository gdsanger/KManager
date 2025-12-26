"""
Views for the kmanager project.
"""
from django.contrib.auth import views as auth_views, logout
from django.shortcuts import redirect
from django.conf import settings


class CustomLogoutView(auth_views.LogoutView):
    """
    Custom logout view that accepts GET, POST, and HEAD requests.
    
    Note: Accepting GET requests for logout creates a potential CSRF vulnerability
    where malicious sites could trigger logout via image tags or links. However,
    this provides better UX for link-based logout in the navigation. Django's
    same-site cookie policy provides some protection in modern browsers.
    
    For production use, consider:
    - Using POST forms with CSRF tokens instead of links
    - Implementing additional security measures
    - Or accepting the trade-off for better UX in a controlled environment
    """
    http_method_names = ['get', 'post', 'head']
    
    def get(self, request, *args, **kwargs):
        """Handle GET request by logging out and redirecting."""
        logout(request)
        next_page = self.next_page or settings.LOGOUT_REDIRECT_URL or '/'
        return redirect(next_page)
