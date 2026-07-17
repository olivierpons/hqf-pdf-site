from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from core.admin import VersionedAdminMixin

from .models import Invoice, Plan, Subscription, UsageRecord


@admin.register(Plan)
class PlanAdmin(VersionedAdminMixin, admin.ModelAdmin):
    """Admin for the offers on sale.

    Editing a price or a quota supersedes the plan and leaves the old row, so an
    invoice already cut keeps the numbers it froze. The changelist lists live
    plans only.
    """

    ordering = ("name",)
    list_display = (
        "name",
        "monthly_price",
        "included_pages",
        "included_requests",
        "overage_page_price",
        "overage_request_price",
    )
    search_fields = ("name",)
    fieldsets = (
        (None, {"fields": ("name", "monthly_price")}),
        (
            _("[included]"),
            {"fields": ("included_pages", "included_requests")},
        ),
        (
            _("[overage rates]"),
            {"fields": ("overage_page_price", "overage_request_price")},
        ),
    )


@admin.register(Subscription)
class SubscriptionAdmin(VersionedAdminMixin, admin.ModelAdmin):
    """Admin for who is on which plan.

    Changing the plan supersedes the subscription. The changelist lists live
    subscriptions only.
    """

    ordering = ("account",)
    list_display = ("account", "plan", "started_on")
    list_filter = ("plan",)
    search_fields = ("account__email", "plan__name")
    autocomplete_fields = ("account",)


@admin.register(UsageRecord)
class UsageRecordAdmin(VersionedAdminMixin, admin.ModelAdmin):
    """Admin for the renders the server reported, read-only.

    The rows are a machine's log, so nothing here is meant to be typed in; the
    fields are shown but not edited. Deleting closes the row rather than
    destroying it, so a period's total stays reproducible.
    """

    ordering = ("-rendered_at",)
    list_display = ("client_name", "account", "pages", "rendered_at", "event_id")
    list_filter = ("client_name",)
    search_fields = ("client_name", "event_id", "account__email")
    readonly_fields = (
        "account",
        "client_name",
        "event_id",
        "rendered_at",
        "pages",
    )


@admin.register(Invoice)
class InvoiceAdmin(VersionedAdminMixin, admin.ModelAdmin):
    """Admin for the closed months.

    The frozen numbers and the totals are shown read-only; only the status moves
    by hand, from drafted through issued to paid, and each move supersedes the
    row. The changelist lists live invoices only.
    """

    ordering = ("-period_start",)
    list_display = (
        "account",
        "period_start",
        "period_end",
        "status",
        "total",
        "currency",
    )
    list_filter = ("status", "currency")
    search_fields = ("account__email",)
    readonly_fields = (
        "account",
        "subscription",
        "period_start",
        "period_end",
        "issued_on",
        "currency",
        "monthly_price",
        "included_pages",
        "included_requests",
        "overage_page_price",
        "overage_request_price",
        "used_pages",
        "used_requests",
        "overage_pages",
        "overage_requests",
        "overage_amount",
        "total",
    )
