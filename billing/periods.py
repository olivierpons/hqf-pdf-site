"""Where a subscription's billing months fall.

A subscription is anchored on the day-of-month it started on: its months run
from that day to the same day of the next month. A month with no such day — the
31st in a 30-day month, the 29th of a common February — ends on its last day
instead. The anchor is not moved, only clamped for the months too short to hold
it, so a 31st-anchored subscription still bills on the 31st every month that has
one.

Pure date arithmetic: no database, and no clock. The caller says which day to
reckon from.
"""

import calendar
from datetime import date, timedelta


def _clamp_to_month(anchor_day, year, month):
    """Return the anchor day within a month, pulled back to its last day.

    Args:
        anchor_day: The day-of-month the subscription is anchored on, 1 to 31.
        year: The year.
        month: The month, 1 to 12.

    Returns:
        date: ``date(year, month, anchor_day)``, or the month's last day when
        the month is shorter than ``anchor_day``.
    """
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, last_day))


def _next_month(year, month):
    """Return the ``(year, month)`` one month after the given one."""
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _previous_month(year, month):
    """Return the ``(year, month)`` one month before the given one."""
    return (year - 1, 12) if month == 1 else (year, month - 1)


def period_containing(anchor_day, reference):
    """Return the ``[start, end)`` billing month ``reference`` falls in.

    Args:
        anchor_day: The subscription's anchor day, 1 to 31.
        reference: The day to place in its period.

    Returns:
        tuple: ``(start, end)`` dates. ``start`` is included and ``end`` is
        excluded; they are one month apart at the anchor, clamped for short
        months.
    """
    this_month = _clamp_to_month(anchor_day, reference.year, reference.month)
    if reference >= this_month:
        end = _clamp_to_month(anchor_day, *_next_month(reference.year, reference.month))
        return this_month, end
    start = _clamp_to_month(
        anchor_day, *_previous_month(reference.year, reference.month)
    )
    return start, this_month


def last_closed_period(anchor_day, on):
    """Return the most recent ``[start, end)`` whose end is on or before ``on``.

    This is the period ready to invoice on ``on``: the one that has just ended,
    not the one still running.

    Args:
        anchor_day: The subscription's anchor day, 1 to 31.
        on: The day the close is reckoned on.

    Returns:
        tuple: ``(start, end)`` of the period that closed on or before ``on``.
    """
    running_start, _running_end = period_containing(anchor_day, on)
    return period_containing(anchor_day, running_start - timedelta(days=1))
