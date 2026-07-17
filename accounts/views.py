from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import SignupForm


def signup(request):
    """Create an account and log the new customer straight in.

    Args:
        request: The current request.

    Returns:
        The dashboard on success, the sign-up form otherwise.
    """
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(reverse("accounts:dashboard"))
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def dashboard(request):
    """Show the account's keys and where its plan stands.

    Args:
        request: The current request.

    Returns:
        The dashboard page.
    """
    return render(request, "accounts/dashboard.html")
