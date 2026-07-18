from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from core.admin import VersionedAdminMixin

from .models import ApiKey


@admin.register(ApiKey)
class ApiKeyAdmin(VersionedAdminMixin, admin.ModelAdmin):
    """Admin for the keys, where a key is read and revoked.

    Deleting a key here revokes it: the delete button and the ``delete_selected`` action
    both close its validity window and leave the row, so what a revoked key rendered
    stays attributable. The changelist lists live keys only.

    Editing a key's entitlements supersedes it, carrying the key value over: the
    customer keeps calling with what they hold, under the rights they now have.

    The key is shown in full: the site is the vault, and a customer who lost theirs is
    told it from here.
    """

    ordering = ("client_name",)
    list_display = (
        "client_name",
        "account",
        "allowed_to_use_its_own_fonts",
        "max_pages",
    )
    list_filter = ("allowed_to_use_its_own_fonts",)
    search_fields = ("client_name", "key", "account__email")
    autocomplete_fields = ("account",)
    readonly_fields = ("key",)
    fieldsets = (
        (None, {"fields": ("account", "client_name", "key")}),
        (
            _("[entitlements]"),
            {"fields": ("allowed_to_use_its_own_fonts", "max_pages")},
        ),
    )
