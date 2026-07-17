from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin for the email-keyed user; the stock one assumes a username.

    Deletion is off: both the ``delete_selected`` action and the delete button
    call the hard delete a versioned row refuses, which the admin surfaces as a
    500. Closing an account is ``soft_delete()``, and no screen asks for it yet.
    """

    ordering = ("email",)
    list_display = ("email", "full_name", "company", "is_staff")
    search_fields = ("email", "full_name", "company")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("[identity]"), {"fields": ("full_name", "company", "vat_number")}),
        (
            _("[permissions]"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups")},
        ),
        (_("[dates]"), {"fields": ("last_login", "date_joined")}),
    )

    def has_delete_permission(self, request, obj=None):
        """Refuse deletion from the admin, whoever asks.

        Args:
            request: The admin request.
            obj: The row being looked at, or None on the changelist.

        Returns:
            bool: Always False.
        """
        return False

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )
