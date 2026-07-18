from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import User


class SignupForm(UserCreationForm):
    """Creates a customer account from the public sign-up page."""

    class Meta:
        model = User
        fields = ("email", "full_name", "company", "vat_number")
        # Explicit labels skip the capfirst Django applies to a verbose_name, so these
        # carry their own capital.
        labels = {
            "company": _("[Company (leave empty if you are an individual)]"),
            "vat_number": _("[VAT number (companies in the EU)]"),
        }
