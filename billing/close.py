"""Turn each subscription's just-closed billing month into a draft invoice.

A subscription is anchored on the day of the month it started on: its months run from
that day to the same day of the next, a short month clamping to its last day (see
:mod:`billing.periods`). Reckoned on a given day, the period that has just closed for
each subscription is billed — but only when the subscription's validity window covers
that period whole. So a cancelled subscription, whose window is set to end at its
period's close, is billed for that final period; and the part-period a plan change
leaves behind, whose window is cut at the day of the change, is not.

Nothing here reads whether a subscription is "live now": it reads the validity dates
every row carries, so a subscription closed after its last period still has it billed.
It bills the one period that just closed, so it is meant to run each period; a
subscription-period already invoiced is skipped, and closing the same day twice adds
nothing.
"""

from django.db.models import Count, Sum

from billing.models import Invoice, Subscription, UsageRecord
from billing.periods import day_start_utc, last_closed_period


def _aware_bounds(start, end):
    """Return ``[start, end)`` as the UTC instants those days begin at.

    Args:
        start: The inclusive first day.
        end: The exclusive last day.

    Returns:
        tuple: The two days as UTC-aware datetimes, so they compare against the
        UTC ``rendered_at`` column on one timeline.
    """
    return day_start_utc(start), day_start_utc(end)


def usage_by_account(start, end):
    """Return ``{account_id: (pages, requests)}`` for renders in the period.

    One grouped query over the live usage rows: pages summed, requests counted (one row
    is one request).

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


def _period_owed(subscription, on):
    """Return the ``[start, end)`` the subscription owes as of ``on``, or None.

    It is the period that closed most recently on or before ``on``, owed only when the
    subscription had already started by it and its validity window covers it to the end
    — so a plan change's part-period, or a period after the subscription lapsed, is not
    owed.

    Args:
        subscription: The subscription version to reckon.
        on: The day the close is reckoned on.

    Returns:
        tuple | None: ``(start, end)`` when a period is owed, else None.
    """
    start, end = last_closed_period(subscription.started_on.day, on)
    if start < subscription.started_on:
        return None
    # The window's end is a UTC instant set to a day's start, so its UTC date is the
    # boundary day — the same day the period edges are reckoned as.
    if subscription.date_v_end is not None and subscription.date_v_end.date() < end:
        return None
    return start, end


def build_invoices(on, issued_on):
    """Return one unsaved draft invoice per subscription owing a closed period.

    Each invoice snapshots its subscription's plan and totals the account's usage over
    the period. A subscription-period already carrying a live invoice is skipped, so a
    re-run adds nothing.

    Queries: one for every subscription version, one usage total per distinct period
    billed, and one for the invoices already cut against these subscriptions. Saving the
    returned invoices is the caller's step.

    Args:
        on: The day the close is reckoned on.
        issued_on: The date to stamp each invoice with.

    Returns:
        tuple: ``(invoices, skipped)`` — the unsaved :class:`Invoice` list and
        the number of subscription-periods already invoiced.
    """
    owed = []
    for subscription in Subscription.history.select_related("plan"):
        period = _period_owed(subscription, on)
        if period is not None:
            owed.append((subscription, *period))
    if not owed:
        return [], 0

    usage = {
        period: usage_by_account(*period)
        for period in {(start, end) for _sub, start, end in owed}
    }
    already = {
        (invoice.subscription_id, invoice.period_start, invoice.period_end)
        for invoice in Invoice.objects.filter(
            subscription_id__in={subscription.pk for subscription, _s, _e in owed}
        )
    }

    invoices = []
    skipped = 0
    for subscription, start, end in owed:
        if (subscription.pk, start, end) in already:
            skipped += 1
            continue
        pages, requests = usage[(start, end)].get(subscription.account_id, (0, 0))
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
