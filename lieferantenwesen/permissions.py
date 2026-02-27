"""
Permission checks for the Lieferantenwesen (supplier management) area.

Access rules:
- Standard access (upload / edit up to IN_REVIEW): staff users or members of
  the "Lieferantenwesen" group.
- Approval access (APPROVED / REJECTED): additionally requires membership in
  the "Geschäftsleitung" group or superuser status.
"""

from django.contrib.auth.decorators import user_passes_test


def user_has_lieferantenwesen_access(user):
    """Return True if the user may use the Lieferantenwesen module."""
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.groups.filter(name__in=["Lieferantenwesen", "Geschäftsleitung"]).exists()


def user_can_approve_invoices(user):
    """Return True if the user may approve or reject incoming invoices."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name="Geschäftsleitung").exists()


def lieferantenwesen_required(function=None):
    """Decorator: requires basic Lieferantenwesen access."""
    actual_decorator = user_passes_test(
        user_has_lieferantenwesen_access,
        login_url=None,
        redirect_field_name="next",
    )
    if function:
        return actual_decorator(function)
    return actual_decorator


def geschaeftsleitung_required(function=None):
    """Decorator: requires Geschäftsleitung / approval access."""
    actual_decorator = user_passes_test(
        user_can_approve_invoices,
        login_url=None,
        redirect_field_name="next",
    )
    if function:
        return actual_decorator(function)
    return actual_decorator
