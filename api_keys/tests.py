import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from api_keys.models import KEY_PREFIX, ApiKey, generate_key


class TestGenerateKey:
    def test_a_key_is_prefixed_and_fits_the_column(self):
        key = generate_key()
        assert key.startswith(KEY_PREFIX)
        assert len(key) <= ApiKey._meta.get_field("key").max_length

    def test_two_keys_never_come_out_the_same(self):
        assert generate_key() != generate_key()

    def test_a_key_carries_nothing_an_nginx_map_would_quote(self):
        key = generate_key()
        assert not set(key) - set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        )


@pytest.mark.django_db
class TestApiKeyModel:
    def test_a_key_is_generated_when_none_is_given(self, api_key):
        assert api_key.key.startswith(KEY_PREFIX)

    def test_a_new_key_is_entitled_to_nothing_beyond_the_defaults(self, api_key):
        assert not api_key.allowed_to_use_its_own_fonts
        assert api_key.max_pages is None

    def test_a_key_reads_as_the_client_the_server_knows(self, api_key):
        assert str(api_key) == "acme"

    def test_a_client_name_an_http_header_could_not_carry_is_refused(self, account):
        key = ApiKey(account=account, client_name="acme corp")
        with pytest.raises(ValidationError):
            key.full_clean()

    def test_a_client_name_escaping_its_font_directory_is_refused(self, account):
        key = ApiKey(account=account, client_name="../../etc")
        with pytest.raises(ValidationError):
            key.full_clean()

    def test_two_live_keys_cannot_share_a_client_name(self, account, api_key):
        with pytest.raises(IntegrityError):
            ApiKey.objects.create(account=account, client_name=api_key.client_name)

    def test_two_live_keys_cannot_share_a_key(self, account, api_key):
        with pytest.raises(IntegrityError):
            ApiKey.objects.create(account=account, client_name="other", key=api_key.key)

    def test_a_revoked_key_frees_its_client_name(self, account, api_key):
        api_key.revoke()
        successor = ApiKey.objects.create(account=account, client_name="acme")
        assert successor.pk != api_key.pk


@pytest.mark.django_db
class TestRevoke:
    def test_revoking_closes_the_window_and_leaves_the_row(self, api_key):
        api_key.revoke()
        assert api_key.date_v_end is not None
        assert ApiKey.history.filter(pk=api_key.pk).exists()

    def test_a_revoked_key_leaves_the_live_set(self, api_key):
        api_key.revoke()
        assert not ApiKey.objects.filter(pk=api_key.pk).exists()

    def test_revoking_twice_keeps_the_first_closing_time(self, api_key):
        api_key.revoke()
        closed_at = api_key.date_v_end
        api_key.revoke()
        assert api_key.date_v_end == closed_at

    def test_revoking_leaves_the_account_alone(self, api_key, account):
        api_key.revoke()
        assert type(account).objects.filter(pk=account.pk).exists()


@pytest.mark.django_db
class TestVersioning:
    def test_granting_a_right_mints_a_successor_and_closes_the_predecessor(
        self, api_key
    ):
        successor = api_key.update(allowed_to_use_its_own_fonts=True)
        assert successor.pk != api_key.pk
        assert successor.allowed_to_use_its_own_fonts
        assert successor.key == api_key.key
        assert ApiKey.history.get(pk=api_key.pk).date_v_end is not None

    def test_the_live_set_holds_the_successor_alone(self, api_key):
        successor = api_key.update(max_pages=50)
        assert list(ApiKey.objects.values_list("pk", flat=True)) == [successor.pk]

    def test_an_in_place_edit_of_an_entitlement_is_refused(self, api_key):
        api_key.max_pages = 10
        with pytest.raises(RuntimeError):
            api_key.save()

    def test_deleting_a_key_is_refused(self, api_key):
        with pytest.raises(RuntimeError):
            api_key.delete()

    def test_a_bulk_soft_delete_closes_every_selected_key(self, account, api_key):
        ApiKey.objects.create(account=account, client_name="other")
        ApiKey.objects.update(date_v_end=timezone.now())
        assert not ApiKey.objects.exists()
        assert ApiKey.history.count() == 2
        assert ApiKey.history.get(pk=api_key.pk).date_v_end is not None

    def test_editing_an_account_carries_its_keys_to_the_successor(
        self, account, api_key
    ):
        successor = account.update(company="Acme SARL")
        assert list(successor.api_keys.values_list("pk", flat=True)) == [api_key.pk]

    def test_destroying_an_account_destroys_its_keys(self, account, api_key):
        type(account).history.filter(pk=account.pk).hard_delete()
        assert not ApiKey.history.filter(pk=api_key.pk).exists()
