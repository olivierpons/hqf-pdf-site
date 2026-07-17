# pytest injects a fixture by matching it to an argument name, so a fixture
# names what it depends on and never reads it: ``db`` opens the transaction
# pytest-django rolls back. Naming it is also what shadows it.
# pylint: disable=unused-argument, redefined-outer-name

import pytest
from django.contrib.auth import get_user_model

from api_keys.models import ApiKey


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
