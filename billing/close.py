"""Turn a billing period's usage into one draft invoice per subscription.

The month a subscription is anchored to closes into an invoice: its account's
renders over the period are totalled, the plan's numbers are frozen onto the
bill, and the overage is worked out. An account already invoiced for the exact
period is skipped, so closing the same period twice adds nothing.

The period is passed in as an explicit ``[start, end)`` date range. Deriving each
subscription's own window from its anchor day — and how to treat a short month or
a mid-period plan change — is not decided here; the caller states the window.
"""

from datetime import datetime, time

from django.db.models import Count, Sum
from django.utils import timezone

from billing.models import Invoice, Subscription, UsageRecord


def _aware_bounds(start, end):
    """Return ``[start, end)`` as aware datetimes at midnight.

    Args:
        start: The inclusive first day.
        end: The exclusive last day.

    Returns:
        tuple: The two dates as timezone-aware datetimes, so they compare
        against a ``rendered_at`` column.
    """
    start_dt = timezone.make_aware(datetime.combine(start, time.min))
    end_dt = timezone.make_aware(datetime.combine(end, time.min))
    return start_dt, end_dt


def usage_by_account(start, end):
    """Return ``{account_id: (pages, requests)}`` for renders in the period.

    One grouped query over the live usage rows: pages summed, requests counted
    (one row is one request).

    Args:
        start: The inclusive first day.
        end: The exclusive last day.

    Returns:
        dict: Account id to its ``(pages, requests)`` total over the period.
    """
    start_dt, end_dt = _aware_bounds(start, end)
    rows = (
        UsageRecord.objects.filter(rendered_at__gte=start_dt, rendered_at__lt=end_dt)
        .values("account")
        .annotate(pages=Sum("pages"), requests=Count("pk"))
    )
    return {row["account"]: (row["pages"], row["requests"]) for row in rows}


def build_period_invoices(start, end, issued_on):
    """Return one unsaved draft invoice per subscription not yet billed.

    Each invoice snapshots its subscription's plan and totals the account's usage
    over ``[start, end)``. An account with a live invoice already covering this
    exact period is skipped.

    Queries: one for the live subscriptions and their plans, one to total usage
    per account, one for the invoices already covering the period. Saving the
    returned invoices is the caller's step.

    Args:
        start: The inclusive first day of the period.
        end: The exclusive last day of the period.
        issued_on: The date to stamp each invoice with.

    Returns:
        tuple: ``(invoices, skipped)`` — the unsaved :class:`Invoice` list and
        the number of accounts already invoiced for the period.
    """
    subscriptions = list(Subscription.objects.select_related("plan").all())
    usage = usage_by_account(start, end)
    already = set(
        Invoice.objects.filter(period_start=start, period_end=end).values_list(
            "account_id", flat=True
        )
    )

    invoices = []
    skipped = 0
    for subscription in subscriptions:
        if subscription.account_id in already:
            skipped += 1
            continue
        pages, requests = usage.get(subscription.account_id, (0, 0))
        plan = subscription.plan
        invoice = Invoice(
            account_id=subscription.account_id,
            subscription=subscription,
            period_start=start,
            period_end=end,
            issued_on=issued_on,
            monthly_price=plan.monthly_price,
            included_pages=plan.included_pages,
            included_requests=plan.included_requests,
            overage_page_price=plan.overage_page_price,
            overage_request_price=plan.overage_request_price,
            used_pages=pages,
            used_requests=requests,
        )
        invoice.recompute_totals()
        invoices.append(invoice)
    return invoices, skipped
