"""The API keys that let a customer call the render server.

The site is the vault: a key is stored here in clear, and nowhere else holds it. The
render server authenticates nobody — nginx matches the key a request carries against a
map the site writes, and forwards the client's name in the ``X-HQF-Client`` header.
Revoking a key therefore means rewriting that map, not telling the server anything.

One key, one client the server knows: the key names it, and the entitlements alongside
it are what the server grants it. Two live keys cannot share a client name, so the file
the server reads never carries a name twice.
"""

import secrets

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel

KEY_PREFIX = "sk_live_"

# The client name reaches the server through an HTTP header and becomes the name of the
# directory holding that client's fonts, so it is held to what is safe in both: no
# separators, no leading dash, nothing to quote.
client_name_validator = RegexValidator(
    r"\A[a-z0-9][a-z0-9_-]{0,63}\Z",
    _(
        "[A client name holds up to 64 lowercase letters, digits, underscores "
        "and dashes, and starts with a letter or a digit.]"
    ),
)


def generate_key():
    """Return a fresh API key.

    Returns:
        str: The prefix followed by 32 random bytes, URL-safe encoded — a value
        an nginx map and an HTTP header both carry unquoted.
    """
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


class ApiKey(BaseModel):
    """One customer's key to the render server, and what it may render.

    Temporally versioned: revoking a key closes its validity window and leaves the row,
    so a key is never reissued and the trail of what called when survives. Editing
    entitlements mints a successor under a new primary key, which the key value follows.

    Attributes:
        account: The customer billed for what this key renders.
        client_name: What the server calls this client. Unique among live keys.
        key: The secret itself, in clear. Whoever holds it may render.
        allowed_to_use_its_own_fonts: Whether the client may draw with fonts of
            its own, embedded in a request or held for it on the server.
        max_pages: The largest document this client may render; None for no
            limit of its own, leaving the server's cap to bind.
    """

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name=_("[account]"),
    )
    client_name = models.CharField(
        _("[client name]"), max_length=64, validators=[client_name_validator]
    )
    key = models.CharField(_("[key]"), max_length=64, default=generate_key)
    allowed_to_use_its_own_fonts = models.BooleanField(
        _("[allowed to use its own fonts]"), default=False
    )
    max_pages = models.PositiveIntegerField(_("[max pages]"), null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = _("[API key]")
        verbose_name_plural = _("[API keys]")
        constraints = [
            models.UniqueConstraint(
                fields=("key",),
                condition=models.Q(date_v_end__isnull=True),
                name="uniq_api_key_when_live",
            ),
            models.UniqueConstraint(
                fields=("client_name",),
                condition=models.Q(date_v_end__isnull=True),
                name="uniq_api_key_client_name_when_live",
            ),
        ]

    def __str__(self):
        return self.client_name

    def revoke(self):
        """Close this key's validity window. Idempotent.

        The key stops being written into the nginx map, and calls carrying it are
        refused from the next reload on. Nothing reaches the render server: it never
        knew the key.
        """
        self.soft_delete()
