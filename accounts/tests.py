import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_normalises_email_and_hashes_password(self):
        user = User.objects.create_user(
            email="Probe@EXAMPLE.COM", password="s3cret-probe-pw", full_name="Probe"
        )
        # normalize_email lowercases the domain only: the local part is
        # case-sensitive per RFC 5321.
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
