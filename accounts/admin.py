from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin for the email-keyed user; the stock one assumes a username.

    Deleting an account here ends its validity window: the delete button and the
    ``delete_selected`` action both route to a soft-delete, so they read as they
    always have and leave the row in place. Erasing one for good is the separate
    "destroy" action.

    The changelist lists live accounts only, so a deleted one leaves it and only
    ``User.history`` still holds it.
    """

    actions = ("destroy_accounts",)
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
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )

    def delete_model(self, request, obj):
        """Close the account the delete button was pressed on.

        Args:
            request: The admin request.
            obj: The account to close.
        """
        obj.soft_delete()

    def delete_queryset(self, request, queryset):
        """Close every account the ``delete_selected`` action was run on.

        One statement, whatever the number of rows.

        Args:
            request: The admin request.
            queryset: The selected accounts.
        """
        queryset.update(date_v_end=timezone.now())

    @admin.action(
        permissions=["destroy"],
        description=_("[Destroy the selected accounts and all their history]"),
    )
    def destroy_accounts(self, request, queryset):
        """Erase every selected account for good, past versions included.

        Destroying only the selected rows would leave their closed predecessors
        behind, and the account would survive in ``history``. Every row sharing
        a selected account's email goes, which is what an erasure request asks
        for. An email a past version no longer carries is out of reach — an
        account edited to a new address keeps its older rows.

        Three queries: the emails, then the collect and the cascading delete.

        Args:
            request: The admin request, told how many rows went.
            queryset: The selected accounts.
        """
        emails = list(queryset.values_list("email", flat=True))
        destroyed, __ = User.history.filter(email__in=emails).hard_delete()
        self.message_user(request, _("[Rows destroyed: {}]").format(destroyed))

    def has_destroy_permission(self, request):
        """Return whether this user may erase an account for good.

        Args:
            request: The admin request.

        Returns:
            bool: True for anyone holding the delete permission, from a group
            or from being a superuser.
        """
        return request.user.has_perm("accounts.delete_user")
