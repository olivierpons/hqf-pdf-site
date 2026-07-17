from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin for the email-keyed user; the stock one assumes a username."""

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
