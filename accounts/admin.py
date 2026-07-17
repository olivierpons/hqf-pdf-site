from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin for the email-keyed user; the stock one assumes a username.

    The stock delete button and ``delete_selected`` action issue a hard delete,
    which a versioned row refuses and the admin then surfaces as a 500. Closing
    an account is the "close" action below, which anyone who may change a user
    may run. The changelist lists live accounts only: a closed one leaves it.
    """

    actions = ("close_accounts",)
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

    @admin.action(
        permissions=["change"], description=_("[Close the selected accounts]")
    )
    def close_accounts(self, request, queryset):
        """Close every selected account, in one statement.

        Closing is what deleting an account means here: the row stays, its
        validity window ends, and it leaves ``User.objects`` — so the account
        can no longer log in and its email is free again.

        Args:
            request: The admin request, told how many rows were closed.
            queryset: The selected accounts, live ones by construction.
        """
        closed = queryset.update(date_v_end=timezone.now())
        self.message_user(request, _("[Accounts closed: {}]").format(closed))

    def has_delete_permission(self, request, obj=None):
        """Refuse destruction from the admin, whoever asks.

        The stock delete path destroys the row rather than closing it, so no
        permission can make it legal here. Closing goes through
        :meth:`close_accounts`.

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
