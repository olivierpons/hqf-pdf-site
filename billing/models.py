"""What a customer is sold, what they used, and what they owe for it.

Four models carry billing, all temporally versioned (see :mod:`core.models.base`):
editing a price or a plan mints a successor and leaves the old row, so an invoice
already issued keeps pointing at the numbers that were true when it was cut.

* :class:`Plan` — an offer on sale. Free, premium, gold or anything else is just another
  row; the range of offers is data, not code.
* :class:`Subscription` — one account on one plan, from a start date whose day-of-month
  is the billing anchor.
* :class:`UsageRecord` — one render the server reported, page count and all. One row is
  one request; the number of requests is how many rows there are.
* :class:`Invoice` — a closed month, with the plan's numbers frozen onto it and the
  used-versus-included overage worked out.

An included quota of ``None`` means *unlimited*, the convention
:attr:`api_keys.models.ApiKey.max_pages` already uses: no cap on that dimension, so it
never runs into overage. Money is stored in the single currency
``settings.BILLING_CURRENCY`` enforces; :class:`Invoice` snapshots the currency against
the day a second one is sold.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from billing.periods import day_start_utc, period_containing
from core.models import BaseModel

# Money rounded to the currency's minor unit. EUR has two decimal places, so a computed
# amount is quantized here before it is stored or shown.
MONEY_QUANTUM = Decimal("0.01")


def default_currency():
    """Return the currency an invoice is cut in.

    Returns:
        str: ``settings.BILLING_CURRENCY``. A plain function, not a lambda, so a
        migration can serialize the field default that calls it.
    """
    return settings.BILLING_CURRENCY


class Plan(BaseModel):
    """An offer on sale: a monthly price, what it includes, and overage rates.

    A quota left as ``None`` is unlimited on that dimension, so that dimension never
    bills overage — a free or a top tier is expressed by the numbers on the row, not by
    a new model. Editing any of them supersedes the plan; invoices already cut keep the
    frozen copies they took.

    Attributes:
        name: What the offer is called. Unique among live plans.
        monthly_price: The recurring price of the plan itself, overage aside.
        included_pages: Pages the monthly price covers; None for unlimited.
        included_requests: Requests the monthly price covers; None for unlimited.
        overage_page_price: Charged per page rendered beyond the included pages;
            None when pages are unlimited.
        overage_request_price: Charged per request beyond the included requests;
            None when requests are unlimited.
    """

    name = models.CharField(_("[plan name]"), max_length=64)
    monthly_price = models.DecimalField(
        _("[monthly price]"), max_digits=10, decimal_places=2
    )
    included_pages = models.PositiveIntegerField(
        _("[included pages]"), null=True, blank=True
    )
    included_requests = models.PositiveIntegerField(
        _("[included requests]"), null=True, blank=True
    )
    overage_page_price = models.DecimalField(
        _("[overage price per page]"),
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )
    overage_request_price = models.DecimalField(
        _("[overage price per request]"),
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    class Meta(BaseModel.Meta):
        verbose_name = _("[plan]")
        verbose_name_plural = _("[plans]")
        constraints = [
            models.UniqueConstraint(
                fields=("name",),
                condition=models.Q(date_v_end__isnull=True),
                name="uniq_plan_name_when_live",
            ),
        ]

    def __str__(self):
        return self.name


class Subscription(BaseModel):
    """One account on one plan, anchored to a start date.

    The day-of-month of ``started_on`` is the billing anchor: a month runs from that day
    to the same day of the next month. An account holds one live subscription at a time;
    switching plans supersedes it.

    Attributes:
        account: The customer this subscription bills.
        plan: The offer they are on. Protected: a plan referenced by a
            subscription is not destroyed out from under it.
        started_on: The day the subscription began, and the monthly anchor.
    """

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("[account]"),
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name=_("[plan]"),
    )
    started_on = models.DateField(_("[started on]"))

    class Meta(BaseModel.Meta):
        verbose_name = _("[subscription]")
        verbose_name_plural = _("[subscriptions]")
        constraints = [
            models.UniqueConstraint(
                fields=("account",),
                condition=models.Q(date_v_end__isnull=True),
                name="uniq_subscription_account_when_live",
            ),
        ]

    def __str__(self):
        return f"{self.account} / {self.plan}"

    def cancel(self, on=None):
        """End the subscription at the close of the period ``on`` falls in.

        It stays valid — usable and billable — until that period's end, and none of it
        is refunded. Setting the validity end is all it takes: the monthly close reads
        that date and bills the final period like any other.

        Args:
            on: The day the cancellation is requested. Defaults to today.
        """
        on = on or timezone.localdate()
        _start, end = period_containing(self.started_on.day, on)
        self.date_v_end = day_start_utc(end)
        self.save(update_fields=["date_v_end"])

    def change_plan(self, new_plan, on=None):
        """Move the account to ``new_plan``, re-anchored on the day of change.

        The current subscription closes now and a fresh one, anchored on ``on``, opens
        on ``new_plan``. The part-period already run is not billed — its period is no
        longer covered to its end — and nothing is prorated. Invoices already cut stay
        attached to the subscription that produced them.

        Args:
            new_plan: The plan to move to.
            on: The day the change takes effect, and the new anchor. Defaults
                to today.

        Returns:
            Subscription: The new subscription.
        """
        on = on or timezone.localdate()
        self.date_v_end = day_start_utc(on)
        self.save(update_fields=["date_v_end"])
        return Subscription.objects.create(
            account=self.account, plan=new_plan, started_on=on
        )


class UsageRecord(BaseModel):
    """One render the server reported, ready to be totted up into an invoice.

    One row is one request; a period's request count is how many rows fall in it, and
    its page count is their pages summed. The render is named by the client the server
    forwarded, not by a foreign key to the key that made it: a key is versioned and its
    primary key moves under it, but this log is append-only and must not move with it.
    The server's own event id is unique among live rows, so a retried push is recorded
    once.

    Attributes:
        account: The customer billed for this render.
        client_name: The client the render server reported it under.
        event_id: The server's identifier for this render, its idempotency key.
        rendered_at: When the server rendered it.
        pages: Pages this render produced.
    """

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_records",
        verbose_name=_("[account]"),
    )
    client_name = models.CharField(_("[client name]"), max_length=64)
    event_id = models.CharField(_("[event id]"), max_length=128)
    rendered_at = models.DateTimeField(_("[rendered at]"))
    pages = models.PositiveIntegerField(_("[pages]"))

    class Meta(BaseModel.Meta):
        verbose_name = _("[usage record]")
        verbose_name_plural = _("[usage records]")
        constraints = [
            models.UniqueConstraint(
                fields=("event_id",),
                condition=models.Q(date_v_end__isnull=True),
                name="uniq_usage_event_id_when_live",
            ),
        ]

    def __str__(self):
        return f"{self.client_name} @ {self.rendered_at:%Y-%m-%d %H:%M}"


class Invoice(BaseModel):
    """A closed billing month, with the plan's numbers frozen onto it.

    The plan's price and quotas are copied here at close, not read live, so a later
    price change never rewrites a bill. Overage on a dimension is what was used beyond
    what was included, and nothing when the plan included it without limit. Recomputing
    totals is arithmetic on the row's own fields — no query.

    Attributes:
        account: The customer billed.
        subscription: The subscription this bill is for. Protected.
        period_start: First day of the billed month.
        period_end: Day the billed month closes.
        issued_on: The day the invoice was cut.
        currency: The currency it is cut in, snapshotted.
        status: Where the invoice is between drafted and paid.
        monthly_price: The plan's monthly price, frozen.
        included_pages: The plan's page quota, frozen; None for unlimited.
        included_requests: The plan's request quota, frozen; None for unlimited.
        overage_page_price: The plan's per-page overage rate, frozen.
        overage_request_price: The plan's per-request overage rate, frozen.
        used_pages: Pages rendered in the period.
        used_requests: Requests made in the period.
        overage_pages: Pages billed beyond the included quota.
        overage_requests: Requests billed beyond the included quota.
        overage_amount: What the overage costs, in the currency's minor unit.
        total: The monthly price plus the overage.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("[draft]")
        ISSUED = "issued", _("[issued]")
        PAID = "paid", _("[paid]")
        CANCELED = "canceled", _("[canceled]")

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("[account]"),
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name=_("[subscription]"),
    )
    period_start = models.DateField(_("[period start]"))
    period_end = models.DateField(_("[period end]"))
    issued_on = models.DateField(_("[issued on]"))
    currency = models.CharField(_("[currency]"), max_length=3, default=default_currency)
    status = models.CharField(
        _("[status]"),
        max_length=8,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    monthly_price = models.DecimalField(
        _("[monthly price]"), max_digits=10, decimal_places=2
    )
    included_pages = models.PositiveIntegerField(
        _("[included pages]"), null=True, blank=True
    )
    included_requests = models.PositiveIntegerField(
        _("[included requests]"), null=True, blank=True
    )
    overage_page_price = models.DecimalField(
        _("[overage price per page]"),
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )
    overage_request_price = models.DecimalField(
        _("[overage price per request]"),
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )
    used_pages = models.PositiveIntegerField(_("[used pages]"), default=0)
    used_requests = models.PositiveIntegerField(_("[used requests]"), default=0)
    overage_pages = models.PositiveIntegerField(_("[overage pages]"), default=0)
    overage_requests = models.PositiveIntegerField(_("[overage requests]"), default=0)
    overage_amount = models.DecimalField(
        _("[overage amount]"), max_digits=12, decimal_places=2, default=Decimal("0")
    )
    total = models.DecimalField(
        _("[total]"), max_digits=12, decimal_places=2, default=Decimal("0")
    )

    class Meta(BaseModel.Meta):
        verbose_name = _("[invoice]")
        verbose_name_plural = _("[invoices]")

    def __str__(self):
        return f"{self.account} {self.period_start:%Y-%m}"

    def recompute_totals(self):
        """Set the overage and total fields from what was used and included.

        A dimension included without limit (quota ``None``) never bills overage. An
        overage rate left ``None`` counts as zero, so an unlimited dimension contributes
        nothing whatever its used count. The amount and the total are quantized to the
        currency's minor unit. In memory only: the caller saves.
        """
        self.overage_pages = _overage_units(self.used_pages, self.included_pages)
        self.overage_requests = _overage_units(
            self.used_requests, self.included_requests
        )
        pages_cost = self.overage_pages * (self.overage_page_price or Decimal("0"))
        requests_cost = self.overage_requests * (
            self.overage_request_price or Decimal("0")
        )
        self.overage_amount = (pages_cost + requests_cost).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
        self.total = (self.monthly_price + self.overage_amount).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )


def _overage_units(used, included):
    """Return how many units fall beyond the included quota.

    Args:
        used: Units consumed in the period.
        included: Units the plan covers, or None for unlimited.

    Returns:
        int: ``used - included`` when that is positive, else 0; and 0 whenever
        ``included`` is None, since an unlimited quota is never exceeded.
    """
    if included is None:
        return 0
    return max(0, used - included)
