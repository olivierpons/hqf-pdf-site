"""Close each subscription's due billing months into draft invoices.

A thin shell over :func:`billing.close.build_invoices`: it reckons the close on a given
day, builds the invoices each subscription owes by then, and either prints them
(``--dry-run``) or saves them in one transaction.
"""

import argparse
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from billing.close import build_invoices
from core.management.base.custom_help_formatter_mixin import CustomHelpFormatterMixin
from core.management.base.out_mixin import OutMixin


def _date(text):
    """Parse a ``YYYY-MM-DD`` argument into a date.

    Args:
        text: The argument value.

    Returns:
        date: The parsed date.

    Raises:
        argparse.ArgumentTypeError: The value is not a ``YYYY-MM-DD`` date.
    """
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


class Command(CustomHelpFormatterMixin, OutMixin, BaseCommand):
    """Total a period's usage and cut one draft invoice per subscription."""

    help = _(
        "[Close a billing period: total each subscription's usage over it and "
        "cut one draft invoice per account, snapshotting the plan. Re-running "
        "adds nothing.]"
    )

    def get_short_help(self):
        """Return the memo shown with ``-h``.

        Left untranslated: the argument alignment is layout, which a msgid must not
        carry.

        Returns:
            str: The short help text.
        """
        cmd = Path(__file__).stem
        return (
            f"{cmd} — cut the draft invoices each subscription owes by a day\n"
            "\n"
            "  -o / --on          Day to reckon the close on (default: today)\n"
            "  -i / --issued-on   Invoice date (default: today)\n"
            "  -d / --dry-run     Print the invoices instead of saving them\n"
            "\n"
            "  Use --help for full documentation."
        )

    def get_epilog(self):
        """Return the examples shown with ``--help``.

        Left untranslated: the example commands are layout, which a msgid must not
        carry.

        Returns:
            str: The epilog text.
        """
        cmd = Path(__file__).stem
        return (
            "Examples:\n"
            "  # Cut every invoice owed as of today:\n"
            f"  python manage.py {cmd}\n"
            "\n"
            "  # See what would be cut as of a given day, saving nothing:\n"
            f"  python manage.py {cmd} --on 2026-07-15 --dry-run"
        )

    def add_arguments(self, parser):
        """Declare the command's arguments, ordered by their short letter.

        Args:
            parser: The argument parser.
        """
        parser.add_argument(
            "-d",
            "--dry-run",
            action="store_true",
            help=_("[Build the invoices and print them instead of saving.]"),
        )
        parser.add_argument(
            "-i",
            "--issued-on",
            type=_date,
            default=None,
            metavar="YYYY-MM-DD",
            help=_("[Invoice date; defaults to today.]"),
        )
        parser.add_argument(
            "-o",
            "--on",
            type=_date,
            default=None,
            metavar="YYYY-MM-DD",
            help=_("[Day to reckon the close on; defaults to today.]"),
        )

    def handle(self, *args, **options):
        """Build the invoices owed by the close day, then print or save them.

        Args:
            *args: Unused.
            **options: Parsed arguments.
        """
        on = options["on"] or timezone.localdate()
        issued_on = options["issued_on"] or timezone.localdate()

        invoices, skipped = build_invoices(on, issued_on)

        if options["dry_run"]:
            for invoice in invoices:
                self.out(
                    f"{invoice.account} "
                    f"{invoice.period_start}..{invoice.period_end}  "
                    f"pages={invoice.used_pages} requests={invoice.used_requests}  "
                    f"total={invoice.total} {invoice.currency}"
                )
            self.out(
                gettext("[Would cut {created} invoice(s), skipped {skipped}.]").format(
                    created=len(invoices), skipped=skipped
                )
            )
            return

        with transaction.atomic():
            for invoice in invoices:
                invoice.save()
        self.out_success(
            gettext(
                "[Cut {created} invoice(s), skipped {skipped} already billed.]"
            ).format(created=len(invoices), skipped=skipped)
        )
