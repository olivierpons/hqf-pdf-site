# pytest injects a fixture by matching it to an argument name, so a fixture
# names what it depends on and never reads it: ``db`` opens the transaction
# pytest-django rolls back.
# pylint: disable=unused-argument

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def account(db):
    """Return a saved, live user."""
    return get_user_model().objects.create_user(
        email="held@example.com", password="s3cret-probe-pw", full_name="Held"
    )
