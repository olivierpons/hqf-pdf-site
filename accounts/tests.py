import pytest
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_normalises_email_and_hashes_password(self):
        user = User.objects.create_user(
            email="Probe@EXAMPLE.COM", password="s3cret-probe-pw", full_name="Probe"
        )
        # normalize_email lowercases the domain only: the local part is case-sensitive
        # per RFC 5321.
        assert user.email == "Probe@example.com"
        assert user.password != "s3cret-probe-pw"
        assert user.check_password("s3cret-probe-pw")
        assert not user.is_staff

    def test_create_user_without_email_is_refused(self):
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="x", full_name="No Mail")

    def test_create_superuser_is_staff_and_superuser(self):
        user = User.objects.create_superuser(
            email="boss@example.com", password="s3cret-probe-pw", full_name="Boss"
        )
        assert user.is_staff
        assert user.is_superuser

    def test_create_superuser_refuses_being_downgraded(self):
        with pytest.raises(ValueError):
            User.objects.create_superuser(
                email="boss@example.com",
                password="x",
                full_name="Boss",
                is_staff=False,
            )

    def test_email_is_unique(self):
        User.objects.create_user(email="dup@example.com", full_name="First")
        with pytest.raises(IntegrityError):
            User.objects.create_user(email="dup@example.com", full_name="Second")

    def test_str_is_the_email(self):
        assert str(User(email="who@example.com", full_name="Who")) == "who@example.com"


@pytest.mark.django_db
class TestVersionedEdit:
    def test_editing_a_field_in_place_is_refused(self, account):
        account.full_name = "Renamed"
        with pytest.raises(RuntimeError, match="full_name"):
            account.save()

    def test_update_closes_the_row_and_inserts_a_successor(self, account):
        original_pk = account.pk
        successor = account.update(full_name="Renamed")

        assert successor.pk != original_pk
        assert successor.full_name == "Renamed"
        assert successor.date_v_end is None
        assert successor.is_live

        closed = User.history.get(pk=original_pk)
        assert closed.date_v_end is not None
        assert closed.full_name == "Held"
        assert not closed.is_live

    def test_update_copies_the_fields_it_was_not_given(self, account):
        successor = account.update(company="Held SARL")
        assert successor.email == "held@example.com"
        assert successor.full_name == "Held"
        assert successor.check_password("s3cret-probe-pw")
        assert successor.date_joined == account.date_joined

    def test_update_reads_the_stored_row_not_the_instance(self, account):
        account.full_name = "Never Written"
        successor = account.update(company="Held SARL")
        assert successor.full_name == "Held"

    def test_only_the_successor_stays_live(self, account):
        account.update(full_name="Renamed")
        assert User.objects.count() == 1
        assert User.history.count() == 2
        assert User.objects.get().full_name == "Renamed"

    def test_the_successor_keeps_the_email(self, account):
        successor = account.update(full_name="Renamed")
        assert successor.email == "held@example.com"
        assert User.objects.get(email="held@example.com").pk == successor.pk

    def test_updating_a_closed_row_is_refused(self, account):
        account.update(full_name="Renamed")
        with pytest.raises(RuntimeError, match="already closed"):
            account.update(full_name="Renamed Twice")

    def test_saving_a_closed_row_is_refused(self, account):
        account.update(full_name="Renamed")
        closed = User.history.get(pk=account.pk)
        closed.full_name = "Rewriting History"
        with pytest.raises(RuntimeError, match="closed"):
            closed.save()

    def test_update_carries_the_groups_over(self, account):
        group = Group.objects.create(name="beta-testers")
        account.groups.add(group)
        successor = account.update(full_name="Renamed")
        assert list(successor.groups.all()) == [group]


@pytest.mark.django_db
class TestSoftDelete:
    def test_soft_delete_hides_the_row_but_history_keeps_it(self, account):
        account.soft_delete()
        assert account.date_v_end is not None
        assert not User.objects.filter(pk=account.pk).exists()
        assert User.history.filter(pk=account.pk).exists()

    def test_soft_delete_is_idempotent(self, account):
        account.soft_delete()
        closed_at = account.date_v_end
        account.soft_delete()
        assert account.date_v_end == closed_at

    def test_a_soft_deleted_account_cannot_log_in(self, account):
        account.soft_delete()
        assert (
            authenticate(email="held@example.com", password="s3cret-probe-pw") is None
        )

    def test_a_soft_deleted_account_frees_its_email(self, account):
        account.soft_delete()
        replacement = User.objects.create_user(
            email="held@example.com", full_name="Held Again"
        )
        assert replacement.pk != account.pk
        assert User.objects.get(email="held@example.com").pk == replacement.pk

    def test_hard_delete_is_refused(self, account):
        with pytest.raises(RuntimeError, match="soft_delete"):
            account.delete()

    @pytest.mark.usefixtures("account")
    def test_queryset_delete_is_refused(self):
        with pytest.raises(RuntimeError, match="soft_delete"):
            User.objects.all().delete()


@pytest.mark.django_db
@pytest.mark.usefixtures("account")
class TestBulkWrites:
    def test_bulk_update_of_a_business_field_is_refused(self):
        with pytest.raises(RuntimeError, match="full_name"):
            User.objects.update(full_name="Renamed In Bulk")

    def test_bulk_soft_delete_is_allowed(self):
        assert User.objects.update(date_v_end=timezone.now()) == 1
        assert not User.objects.exists()
        assert User.history.count() == 1


@pytest.mark.django_db
class TestAdminEditSupersedesTheAccount:
    def change_url(self, account):
        return reverse("admin:accounts_user_change", args=[account.pk])

    def form(self, **overrides):
        """Return a filled change form, since the admin posts every field."""
        fields = {
            "email": "held@example.com",
            "full_name": "Held",
            "company": "",
            "vat_number": "",
            "is_active": "on",
            "last_login_0": "",
            "last_login_1": "",
            "date_joined_0": "2026-07-17",
            "date_joined_1": "10:00:00",
        }
        fields.update(overrides)
        return fields

    def test_saving_an_edit_closes_the_row_and_inserts_a_successor(
        self, boss_client, account
    ):
        response = boss_client.post(
            self.change_url(account), self.form(full_name="Renamed Here")
        )
        assert response.status_code == 302

        assert User.history.get(pk=account.pk).date_v_end is not None
        successor = User.objects.get(email="held@example.com")
        assert successor.pk != account.pk
        assert successor.full_name == "Renamed Here"

    def test_saving_an_edit_keeps_the_password_the_account_logs_in_with(
        self, boss_client, account
    ):
        boss_client.post(self.change_url(account), self.form(full_name="Renamed Here"))
        assert authenticate(email="held@example.com", password="s3cret-probe-pw")

    def test_the_groups_an_edit_grants_land_on_the_successor(
        self, boss_client, account
    ):
        squad = Group.objects.create(name="squad")
        boss_client.post(
            self.change_url(account),
            self.form(full_name="Renamed Here", groups=[str(squad.pk)]),
        )
        successor = User.objects.get(email="held@example.com")
        assert list(successor.groups.values_list("name", flat=True)) == ["squad"]

    def test_saving_and_carrying_on_lands_on_the_successor(self, boss_client, account):
        response = boss_client.post(
            self.change_url(account),
            self.form(full_name="Renamed Here", _continue="1"),
        )
        successor = User.objects.get(email="held@example.com")
        assert response.status_code == 302
        assert response.url == self.change_url(successor)
        assert boss_client.get(response.url).status_code == 200


@pytest.mark.django_db
class TestAdminDeleteOnlyClosesTheAccount:
    def test_the_delete_button_closes_the_account(self, client, account):
        boss = User.objects.create_superuser(
            email="boss@example.com", password="s3cret-probe-pw", full_name="Boss"
        )
        client.force_login(boss)
        response = client.post(
            reverse("admin:accounts_user_delete", args=[account.pk]), {"post": "yes"}
        )
        assert response.status_code == 302

        # The row is still there; only its validity window ended.
        assert User.history.get(pk=account.pk).date_v_end is not None
        assert not User.objects.filter(pk=account.pk).exists()
        assert (
            authenticate(email="held@example.com", password="s3cret-probe-pw") is None
        )

    def test_the_delete_action_closes_the_accounts(self, client, account):
        boss = User.objects.create_superuser(
            email="boss@example.com", password="s3cret-probe-pw", full_name="Boss"
        )
        client.force_login(boss)
        response = client.post(
            reverse("admin:accounts_user_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [str(account.pk)],
                "post": "yes",
            },
        )
        assert response.status_code == 302
        assert User.history.get(pk=account.pk).date_v_end is not None
        assert not User.objects.filter(pk=account.pk).exists()

    def test_deleting_needs_more_than_a_look(self, client, account):
        watcher = User.objects.create_user(
            email="watcher@example.com",
            password="s3cret-probe-pw",
            full_name="Watcher",
            is_staff=True,
        )
        watcher.user_permissions.add(
            Permission.objects.get(
                codename="view_user", content_type__app_label="accounts"
            )
        )
        client.force_login(watcher)
        client.post(
            reverse("admin:accounts_user_delete", args=[account.pk]), {"post": "yes"}
        )
        assert User.objects.filter(pk=account.pk).exists()


@pytest.mark.django_db
class TestAdminDestroysAccounts:
    def test_destroying_takes_the_history_with_it(self, client, account):
        successor = account.update(full_name="Renamed")
        assert User.history.count() == 2

        boss = User.objects.create_superuser(
            email="boss@example.com", password="s3cret-probe-pw", full_name="Boss"
        )
        client.force_login(boss)
        response = client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "destroy_accounts", "_selected_action": [str(successor.pk)]},
        )
        assert response.status_code == 302

        # The closed predecessor goes too, or the account would survive in history and
        # the erasure would be a lie.
        assert not User.history.filter(email="held@example.com").exists()
        assert User.history.count() == 1

    def test_destroying_needs_the_delete_permission(self, client, account):
        editor = User.objects.create_user(
            email="editor@example.com",
            password="s3cret-probe-pw",
            full_name="Editor",
            is_staff=True,
        )
        editor.user_permissions.add(
            Permission.objects.get(
                codename="change_user", content_type__app_label="accounts"
            )
        )
        client.force_login(editor)
        client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "destroy_accounts", "_selected_action": [str(account.pk)]},
        )
        assert User.history.filter(pk=account.pk).exists()

    def test_a_group_grants_the_destroy_permission(self, client, account):
        squad = Group.objects.create(name="admins")
        squad.permissions.add(
            Permission.objects.get(
                codename="delete_user", content_type__app_label="accounts"
            ),
            Permission.objects.get(
                codename="view_user", content_type__app_label="accounts"
            ),
        )
        member = User.objects.create_user(
            email="member@example.com",
            password="s3cret-probe-pw",
            full_name="Member",
            is_staff=True,
        )
        member.groups.add(squad)
        client.force_login(member)
        response = client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "destroy_accounts", "_selected_action": [str(account.pk)]},
        )
        assert response.status_code == 302
        assert not User.history.filter(pk=account.pk).exists()


@pytest.mark.django_db
class TestLastLogin:
    def test_logging_in_writes_last_login_without_versioning(self, client, account):
        assert account.last_login is None

        assert client.login(email="held@example.com", password="s3cret-probe-pw")

        assert User.history.count() == 1
        account.refresh_from_db()
        assert account.last_login is not None
        assert client.session["_auth_user_id"] == str(account.pk)


@pytest.mark.django_db
class TestSignup:
    def test_signup_creates_the_account_and_logs_it_in(self, client):
        response = client.post(
            reverse("accounts:signup"),
            {
                "email": "new@example.com",
                "full_name": "New Person",
                "company": "New SARL",
                "vat_number": "FR12345678901",
                "password1": "correct-horse-battery-staple-42",
                "password2": "correct-horse-battery-staple-42",
            },
        )
        assert response.status_code == 302
        assert response.url == reverse("accounts:dashboard")

        user = User.objects.get(email="new@example.com")
        assert user.company == "New SARL"
        assert client.session["_auth_user_id"] == str(user.pk)

    def test_signup_rejects_mismatched_passwords(self, client):
        response = client.post(
            reverse("accounts:signup"),
            {
                "email": "new@example.com",
                "full_name": "New Person",
                "password1": "correct-horse-battery-staple-42",
                "password2": "a-different-password-entirely",
            },
        )
        assert response.status_code == 200
        assert not User.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db
class TestDashboard:
    def test_dashboard_redirects_anonymous_visitors_to_login(self, client):
        response = client.get(reverse("accounts:dashboard"))
        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_dashboard_shows_the_account(self, client):
        User.objects.create_user(
            email="seen@example.com", password="s3cret-probe-pw", full_name="Seen"
        )
        client.login(email="seen@example.com", password="s3cret-probe-pw")
        response = client.get(reverse("accounts:dashboard"))
        assert response.status_code == 200
        assert b"seen@example.com" in response.content
