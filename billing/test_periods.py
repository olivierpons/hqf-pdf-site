"""The billing-period arithmetic: anchors, short months, and what has closed."""

from datetime import date

from billing.periods import last_closed_period, period_containing


class TestPeriodContaining:
    """The ``[start, end)`` month a day falls in, anchored on a day-of-month."""

    def test_a_mid_month_anchor_runs_day_to_day(self):
        start, end = period_containing(14, date(2026, 1, 20))
        assert (start, end) == (date(2026, 1, 14), date(2026, 2, 14))

    def test_the_anchor_day_itself_starts_a_new_period(self):
        start, end = period_containing(14, date(2026, 1, 14))
        assert (start, end) == (date(2026, 1, 14), date(2026, 2, 14))

    def test_the_day_before_the_anchor_is_the_previous_period(self):
        start, end = period_containing(14, date(2026, 1, 13))
        assert (start, end) == (date(2025, 12, 14), date(2026, 1, 14))

    def test_a_31st_anchor_clamps_to_the_last_day_of_february(self):
        # February has no 31st, so the period ends on its last day.
        start, end = period_containing(31, date(2026, 2, 10))
        assert (start, end) == (date(2026, 1, 31), date(2026, 2, 28))

    def test_a_31st_anchor_returns_to_the_31st_after_a_short_month(self):
        start, end = period_containing(31, date(2026, 3, 1))
        assert (start, end) == (date(2026, 2, 28), date(2026, 3, 31))

    def test_a_31st_anchor_in_a_leap_february(self):
        start, end = period_containing(31, date(2024, 2, 15))
        assert (start, end) == (date(2024, 1, 31), date(2024, 2, 29))

    def test_the_period_crosses_the_year_boundary(self):
        start, end = period_containing(15, date(2025, 12, 20))
        assert (start, end) == (date(2025, 12, 15), date(2026, 1, 15))


class TestLastClosedPeriod:
    """The period ready to invoice: the one just ended, not the one running."""

    def test_it_is_the_period_before_the_running_one(self):
        # On the 20th, the period that started on the 14th is still running; the one
        # that closed is the month before it.
        start, end = last_closed_period(14, date(2026, 2, 20))
        assert (start, end) == (date(2026, 1, 14), date(2026, 2, 14))

    def test_on_the_anchor_day_the_period_that_just_ended_is_closed(self):
        # The 14th ends one period and opens the next; what closed is the one ending
        # today.
        start, end = last_closed_period(14, date(2026, 2, 14))
        assert (start, end) == (date(2026, 1, 14), date(2026, 2, 14))

    def test_it_clamps_across_a_short_month(self):
        start, end = last_closed_period(31, date(2026, 3, 15))
        assert (start, end) == (date(2026, 1, 31), date(2026, 2, 28))
