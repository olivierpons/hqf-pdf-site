from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, LiveManager


class UserManager(BaseUserManager, LiveManager):
    """Creates users keyed by email, since :class:`User` has no username.

    Inherits :class:`~core.models.LiveManager` so ``User.objects`` — and with it
    ``get_by_natural_key``, hence authentication — sees live rows only: a
    soft-deleted account cannot log in, and a superseded one is never returned.
    """

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        """Create a customer account.

        Args:
            email: Login identifier, normalised before storage.
            password: Raw password, hashed before saving. None yields an
                unusable password, blocking password login.
            **extra_fields: Any other :class:`User` field.

        Returns:
            The saved user.

        Raises:
            ValueError: If email is empty.
        """
        if not email:
            raise ValueError("A user needs an email address")
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create an account with full admin rights.

        Args:
            email: Login identifier.
            password: Raw password, hashed before saving.
            **extra_fields: Any other :class:`User` field.

        Returns:
            The saved superuser.

        Raises:
            ValueError: If is_staff or is_superuser is passed as False.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("A superuser is both staff and superuser")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser, BaseModel):
    """A customer account, identified by email.

    A customer signs up with an email and pays by bank transfer; a username
    would name nothing the email does not already name.

    Temporally versioned, so editing an account closes its row and inserts a
    successor under a **new primary key**. A session stores the primary key it
    logged in with, so a view editing the current user re-issues
    ``login(request, successor)`` or logs them out.

    ``date_joined`` records when the account was opened and is copied onto each
    successor; ``date_v_start`` records when that particular row opened.
    """

    # ``last_login`` is written by Django's ``user_logged_in`` signal, in place
    # and out of our reach. Versioning it would mint a new primary key on every
    # login and invalidate the session being established.
    EXTRA_IN_PLACE_FIELDS = frozenset({"last_login"})

    username = None
    first_name = None
    last_name = None

    email = models.EmailField(_("[email address]"))
    # An invoice carries a name, and for a company a VAT number.
    full_name = models.CharField(_("[full name]"), max_length=200)
    company = models.CharField(_("[company]"), max_length=200, blank=True)
    vat_number = models.CharField(_("[VAT number]"), max_length=30, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta(BaseModel.Meta):
        verbose_name = _("[user]")
        verbose_name_plural = _("[users]")
        constraints = [
            models.UniqueConstraint(
                fields=("email",),
                condition=models.Q(date_v_end__isnull=True),
                name="uniq_user_email_when_live",
            ),
        ]

    def __str__(self):
        return self.email
