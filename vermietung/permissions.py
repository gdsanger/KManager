"""
Permission checks for Vermietung (Rental Management) area.

Access is granted to:
- Users with is_staff=True
- Users in the "Vermietung" group
"""

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied


def user_has_vermietung_access(user):
    """
    Check if user has access to Vermietung area.
    
    Access is granted to:
    - Staff users (is_staff=True)
    - Users in the "Vermietung" group
    
    Args:
        user: Django User object
        
    Returns:
        bool: True if user has access, False otherwise
    """
    if not user.is_authenticated:
        return False
    
    # Staff users always have access
    if user.is_staff:
        return True
    
    # Check if user is in Vermietung group
    return user.groups.filter(name='Vermietung').exists()


def vermietung_required(function=None):
    """
    Decorator for views that checks if user has Vermietung access.
    
    Usage:
        @vermietung_required
        def my_view(request):
            ...
    
    Args:
        function: The view function to decorate
    
    Returns:
        Decorated function
    """
    actual_decorator = user_passes_test(
        user_has_vermietung_access,
        login_url=None,  # Use default LOGIN_URL from settings
        redirect_field_name='next'
    )
    
    if function:
        return actual_decorator(function)
    return actual_decorator


class VermietungAccessMixin(UserPassesTestMixin):
    """
    Mixin for class-based views that require Vermietung access.
    
    Usage:
        class MyView(VermietungAccessMixin, TemplateView):
            ...
    """
    permission_denied_message = "Sie haben keine Berechtigung für den Vermietung-Bereich."
    
    def test_func(self):
        """Check if user has Vermietung access."""
        return user_has_vermietung_access(self.request.user)
