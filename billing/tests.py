import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from billing.models import Invoice, Plan, Subscription, UsageRecord, default_currency

PERIOD_START = date(2026, 6, 15)
PERIOD_END = date(2026, 7, 15)


def _usage(account, event_id, pages, rendered_at):
    """Create one usage row for ``account`` at ``rendered_at``."""
    return UsageRecord.objects.create(
        account=account,
        client_name="acme",
        event_id=event_id,
        rendered_at=rendered_at,
        pages=pages,
    )


def _in_period(day=20, hour=10):
    """Return an aware datetime inside the June period."""
    return timezone.make_aware(datetime(2026, 6, day, hour))


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


def _event(client_name="acme", event_id="evt-1", pages=3, rendered_at=None):
    """Return one usage event as the render server would push it."""
    return {
        "client_name": client_name,
        "event_id": event_id,
        "rendered_at": rendered_at or "2026-06-20T10:00:00+00:00",
        "pages": pages,
    }


def _post(client, events, token=None):
    """POST an events batch to the usage feed with the shared token header."""
    if token is None:
        token = settings.PDF_SERVER_USAGE_TOKEN
    return client.post(
        reverse("billing:ingest_usage"),
        data=json.dumps({"events": events}),
        content_type="application/json",
        headers={"X-HQF-Usage-Token": token},
    )


@pytest.mark.django_db
class TestIngestUsage:
    @pytest.fixture(autouse=True)
    def live_key(self, api_key):
        """Make the live 'acme' key exist, the client the endpoint resolves."""
        return api_key

    def test_a_reported_render_becomes_a_usage_row(self, client, api_key):
        response = _post(client, [_event(pages=7)])
        assert response.status_code == 200
        assert response.json() == {"created": 1, "duplicates": 0}
        row = UsageRecord.objects.get(event_id="evt-1")
        assert row.account == api_key.account
        assert row.pages == 7

    def test_a_batch_records_every_event(self, client):
        response = _post(
            client,
            [
                _event(event_id="evt-1"),
                _event(event_id="evt-2"),
                _event(event_id="evt-3"),
            ],
        )
        assert response.json() == {"created": 3, "duplicates": 0}
        assert UsageRecord.objects.count() == 3

    def test_a_wrong_token_is_refused_and_writes_nothing(self, client):
        response = _post(client, [_event()], token="not-the-secret")
        assert response.status_code == 401
        assert not UsageRecord.objects.exists()

    def test_a_missing_token_is_refused(self, client):
        response = client.post(
            reverse("billing:ingest_usage"),
            data=json.dumps({"events": [_event()]}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_a_get_is_refused(self, client):
        response = client.get(reverse("billing:ingest_usage"))
        assert response.status_code == 405

    def test_a_body_that_is_not_json_is_refused(self, client):
        response = client.post(
            reverse("billing:ingest_usage"),
            data="not json",
            content_type="application/json",
            headers={"X-HQF-Usage-Token": settings.PDF_SERVER_USAGE_TOKEN},
        )
        assert response.status_code == 400

    def test_events_must_be_a_list(self, client):
        response = client.post(
            reverse("billing:ingest_usage"),
            data=json.dumps({"events": "nope"}),
            content_type="application/json",
            headers={"X-HQF-Usage-Token": settings.PDF_SERVER_USAGE_TOKEN},
        )
        assert response.status_code == 400

    def test_an_unknown_client_refuses_the_whole_batch(self, client):
        response = _post(
            client,
            [_event(event_id="evt-1"), _event(client_name="ghost", event_id="evt-2")],
        )
        assert response.status_code == 400
        assert "ghost" in response.json()["clients"]
        assert not UsageRecord.objects.exists()

    def test_a_revoked_client_is_unknown(self, client, api_key):
        api_key.revoke()
        response = _post(client, [_event()])
        assert response.status_code == 400
        assert not UsageRecord.objects.exists()

    def test_a_retried_push_is_counted_not_duplicated(self, client):
        _post(client, [_event(event_id="evt-1")])
        response = _post(client, [_event(event_id="evt-1")])
        assert response.json() == {"created": 0, "duplicates": 1}
        assert UsageRecord.objects.filter(event_id="evt-1").count() == 1

    def test_a_duplicate_within_a_batch_lands_once(self, client):
        response = _post(
            client, [_event(event_id="evt-1"), _event(event_id="evt-1", pages=99)]
        )
        assert response.json() == {"created": 1, "duplicates": 1}
        assert UsageRecord.objects.filter(event_id="evt-1").count() == 1

    def test_a_negative_page_count_is_refused(self, client):
        response = _post(client, [_event(pages=-1)])
        assert response.status_code == 400
        assert not UsageRecord.objects.exists()

    def test_a_missing_field_is_refused(self, client):
        response = _post(client, [{"client_name": "acme", "pages": 3}])
        assert response.status_code == 400

    def test_an_unparseable_timestamp_is_refused(self, client):
        response = _post(client, [_event(rendered_at="not-a-date")])
        assert response.status_code == 400

    def test_a_naive_timestamp_is_made_aware(self, client):
        response = _post(client, [_event(rendered_at="2026-06-20T10:00:00")])
        assert response.status_code == 200
        assert timezone.is_aware(UsageRecord.objects.get(event_id="evt-1").rendered_at)


@pytest.mark.django_db
class TestCloseBillingMonth:
    @pytest.fixture(autouse=True)
    def live_subscription(self, subscription):
        """Put the account on a plan, the subscription the close invoices."""
        return subscription

    def _close(self, **overrides):
        options = {"start": PERIOD_START, "end": PERIOD_END}
        options.update(overrides)
        call_command("close_billing_month", **options)

    def test_it_cuts_a_draft_invoice_totalling_the_period_usage(self, account):
        _usage(account, "evt-1", pages=3, rendered_at=_in_period(day=16))
        _usage(account, "evt-2", pages=5, rendered_at=_in_period(day=28))
        self._close()
        invoice = Invoice.objects.get(account=account)
        assert invoice.status == Invoice.Status.DRAFT
        assert invoice.used_requests == 2
        assert invoice.used_pages == 8
        assert invoice.period_start == PERIOD_START
        assert invoice.period_end == PERIOD_END

    def test_usage_outside_the_period_is_left_out(self, account):
        _usage(
            account,
            "before",
            pages=4,
            rendered_at=timezone.make_aware(datetime(2026, 6, 14, 23)),
        )
        _usage(
            account,
            "after",
            pages=4,
            rendered_at=timezone.make_aware(datetime(2026, 7, 15, 0)),
        )
        _usage(account, "inside", pages=9, rendered_at=_in_period())
        self._close()
        invoice = Invoice.objects.get(account=account)
        assert invoice.used_requests == 1
        assert invoice.used_pages == 9

    def test_a_subscription_with_no_usage_still_gets_a_flat_invoice(self, account):
        self._close()
        invoice = Invoice.objects.get(account=account)
        assert invoice.used_pages == 0
        assert invoice.used_requests == 0
        assert invoice.total == Decimal("49.00")

    def test_overage_beyond_the_quota_lands_on_the_invoice(self, account):
        _usage(account, "big", pages=1500, rendered_at=_in_period())
        for extra in range(1, 501):
            _usage(account, f"req-{extra}", pages=0, rendered_at=_in_period())
        self._close()
        invoice = Invoice.objects.get(account=account)
        # 501 requests over the 500 quota, 1500 pages over the 1000 quota
        assert invoice.overage_pages == 500
        assert invoice.overage_requests == 1

    def test_re_running_the_close_bills_nothing_new(self, account):
        _usage(account, "evt-1", pages=3, rendered_at=_in_period())
        self._close()
        self._close()
        assert Invoice.objects.filter(account=account).count() == 1

    def test_a_dry_run_saves_nothing(self, account):
        _usage(account, "evt-1", pages=3, rendered_at=_in_period())
        self._close(dry_run=True)
        assert not Invoice.objects.exists()

    def test_the_end_must_be_after_the_start(self):
        with pytest.raises(CommandError):
            self._close(start=PERIOD_END, end=PERIOD_START)
