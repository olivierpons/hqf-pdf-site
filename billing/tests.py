from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from billing.models import Invoice, Plan, Subscription, UsageRecord, default_currency


def _invoice(account, subscription, plan, **overrides):
    """Return an unsaved invoice with the plan's numbers frozen onto it."""
    fields = {
        "account": account,
        "subscription": subscription,
        "period_start": date(2026, 6, 15),
        "period_end": date(2026, 7, 15),
        "issued_on": date(2026, 7, 15),
        "monthly_price": plan.monthly_price,
        "included_pages": plan.included_pages,
        "included_requests": plan.included_requests,
        "overage_page_price": plan.overage_page_price,
        "overage_request_price": plan.overage_request_price,
    }
    fields.update(overrides)
    return Invoice(**fields)


@pytest.mark.django_db
class TestPlanModel:
    def test_an_offer_reads_as_its_name(self, plan):
        assert str(plan) == "Starter"

    def test_two_live_plans_cannot_share_a_name(self, plan):
        with pytest.raises(IntegrityError):
            Plan.objects.create(name=plan.name, monthly_price=Decimal("9.00"))

    def test_a_retired_plan_frees_its_name(self, plan):
        plan.soft_delete()
        successor = Plan.objects.create(name="Starter", monthly_price=Decimal("9.00"))
        assert successor.pk != plan.pk

    def test_a_plan_may_include_pages_and_requests_without_limit(self):
        free = Plan.objects.create(
            name="Free",
            monthly_price=Decimal("0.00"),
            included_pages=None,
            included_requests=None,
        )
        assert free.included_pages is None
        assert free.included_requests is None


@pytest.mark.django_db
class TestSubscriptionModel:
    def test_a_subscription_reads_as_account_over_plan(self, subscription):
        assert str(subscription) == f"{subscription.account} / Starter"

    def test_an_account_holds_one_live_subscription(self, subscription, plan):
        with pytest.raises(IntegrityError):
            Subscription.objects.create(
                account=subscription.account, plan=plan, started_on=date(2026, 2, 1)
            )

    def test_ending_a_subscription_lets_the_account_take_another(
        self, account, subscription, plan
    ):
        subscription.soft_delete()
        again = Subscription.objects.create(
            account=account, plan=plan, started_on=date(2026, 3, 1)
        )
        assert again.pk != subscription.pk

    def test_switching_plans_mints_a_successor(self, subscription):
        gold = Plan.objects.create(name="Gold", monthly_price=Decimal("199.00"))
        successor = subscription.update(plan=gold)
        assert successor.pk != subscription.pk
        assert successor.plan == gold


@pytest.mark.django_db
class TestUsageRecordModel:
    def test_a_retried_push_is_recorded_once(self, account):
        UsageRecord.objects.create(
            account=account,
            client_name="acme",
            event_id="evt-1",
            rendered_at=timezone.now(),
            pages=3,
        )
        with pytest.raises(IntegrityError):
            UsageRecord.objects.create(
                account=account,
                client_name="acme",
                event_id="evt-1",
                rendered_at=timezone.now(),
                pages=3,
            )

    def test_a_period_counts_one_request_per_row(self, account):
        for index in range(4):
            UsageRecord.objects.create(
                account=account,
                client_name="acme",
                event_id=f"evt-{index}",
                rendered_at=timezone.now(),
                pages=index + 1,
            )
        rows = UsageRecord.objects.filter(account=account)
        assert rows.count() == 4
        assert sum(row.pages for row in rows) == 10


@pytest.mark.django_db
class TestInvoiceTotals:
    def test_within_the_quota_only_the_monthly_price_is_owed(
        self, account, subscription, plan
    ):
        invoice = _invoice(
            account, subscription, plan, used_pages=800, used_requests=400
        )
        invoice.recompute_totals()
        assert invoice.overage_pages == 0
        assert invoice.overage_requests == 0
        assert invoice.overage_amount == Decimal("0.00")
        assert invoice.total == Decimal("49.00")

    def test_overage_bills_each_dimension_beyond_its_quota(
        self, account, subscription, plan
    ):
        invoice = _invoice(
            account, subscription, plan, used_pages=1500, used_requests=700
        )
        invoice.recompute_totals()
        assert invoice.overage_pages == 500
        assert invoice.overage_requests == 200
        # 500 * 0.01 + 200 * 0.05 = 5.00 + 10.00
        assert invoice.overage_amount == Decimal("15.00")
        assert invoice.total == Decimal("64.00")

    def test_an_unlimited_page_quota_never_bills_page_overage(
        self, account, subscription, plan
    ):
        invoice = _invoice(
            account,
            subscription,
            plan,
            included_pages=None,
            overage_page_price=None,
            used_pages=10_000,
            used_requests=400,
        )
        invoice.recompute_totals()
        assert invoice.overage_pages == 0
        assert invoice.overage_amount == Decimal("0.00")
        assert invoice.total == Decimal("49.00")

    def test_an_unlimited_request_quota_never_bills_request_overage(
        self, account, subscription, plan
    ):
        invoice = _invoice(
            account,
            subscription,
            plan,
            included_requests=None,
            overage_request_price=None,
            used_pages=800,
            used_requests=10_000,
        )
        invoice.recompute_totals()
        assert invoice.overage_requests == 0
        assert invoice.total == Decimal("49.00")

    def test_the_amount_is_quantized_to_the_currencys_minor_unit(
        self, account, subscription, plan
    ):
        invoice = _invoice(
            account,
            subscription,
            plan,
            overage_page_price=Decimal("0.003333"),
            used_pages=1001,
            used_requests=500,
        )
        invoice.recompute_totals()
        # one page over at 0.003333 rounds to 0.00, so nothing is added
        assert invoice.overage_pages == 1
        assert invoice.overage_amount == Decimal("0.00")
        assert invoice.total == Decimal("49.00")


@pytest.mark.django_db
class TestInvoiceModel:
    def test_a_fresh_invoice_is_a_draft(self, account, subscription, plan):
        invoice = _invoice(account, subscription, plan)
        invoice.save()
        assert invoice.status == Invoice.Status.DRAFT

    def test_an_invoice_is_cut_in_the_configured_currency(
        self, account, subscription, plan
    ):
        invoice = _invoice(account, subscription, plan)
        invoice.save()
        assert invoice.currency == "EUR"

    def test_marking_an_invoice_paid_mints_a_successor(
        self, account, subscription, plan
    ):
        invoice = _invoice(account, subscription, plan)
        invoice.save()
        successor = invoice.update(status=Invoice.Status.PAID)
        assert successor.pk != invoice.pk
        assert successor.status == Invoice.Status.PAID

    def test_editing_the_plan_leaves_a_cut_invoice_untouched(
        self, account, subscription, plan
    ):
        invoice = _invoice(account, subscription, plan)
        invoice.save()
        plan.update(monthly_price=Decimal("99.00"))
        invoice.refresh_from_db()
        assert invoice.monthly_price == Decimal("49.00")


class TestDefaultCurrency:
    def test_it_reads_the_configured_currency(self):
        assert default_currency() == "EUR"
