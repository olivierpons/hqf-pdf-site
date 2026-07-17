# pytest injects a fixture by matching it to an argument name, so a fixture
# names what it depends on and never reads it: ``db`` opens the transaction
# pytest-django rolls back. Naming it is also what shadows it.
# pylint: disable=unused-argument, redefined-outer-name

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from api_keys.models import ApiKey
from billing.models import Plan, Subscription


@pytest.fixture
def account(db):
    """Return a saved, live user."""
    return get_user_model().objects.create_user(
        email="held@example.com", password="s3cret-probe-pw", full_name="Held"
    )


@pytest.fixture
def api_key(account):
    """Return a saved, live key belonging to ``account``."""
    return ApiKey.objects.create(account=account, client_name="acme")


@pytest.fixture
def plan(db):
    """Return a saved plan: 1000 pages and 500 requests a month, then overage."""
    return Plan.objects.create(
        name="Starter",
        monthly_price=Decimal("49.00"),
        included_pages=1000,
        included_requests=500,
        overage_page_price=Decimal("0.010000"),
        overage_request_price=Decimal("0.050000"),
    )


@pytest.fixture
def subscription(account, plan):
    """Return ``account`` subscribed to ``plan`` from a fixed anchor day."""
    return Subscription.objects.create(
        account=account, plan=plan, started_on=date(2026, 1, 15)
    )


@pytest.fixture
def boss_client(client, db):
    """Return a test client logged in as a superuser.

    pytest-django's own ``admin_client`` builds its user with a username, which
    this project's email-keyed model has not, so it cannot be used here.
    """
    boss = get_user_model().objects.create_superuser(
        email="boss@example.com", password="s3cret-probe-pw", full_name="Boss"
    )
    client.force_login(boss)
    return client
