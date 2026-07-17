"""Write the render server's front from the site's live API keys.

The site holds every key and its rights. This turns them into the two files the
front reads: the server's ``clients.toml`` and nginx's key-to-client map. It
writes both atomically, so a reader never sees a half-written file.

The files take effect on the next reload: the server reads its clients file at
startup, nginx reads its map on reload. This command touches neither service —
reloading them is the operator's step.
"""

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from api_keys.models import ApiKey
from api_keys.server_config import render_clients_toml, render_nginx_map
from core.management.base.custom_help_formatter_mixin import CustomHelpFormatterMixin
from core.management.base.out_mixin import OutMixin


def _write_atomically(path, contents):
    """Replace ``path`` with ``contents`` in one indivisible step.

    The contents land in a temporary file beside the target, which is then
    renamed over it: a reader sees either the old file or the new one, never a
    partial write.

    Args:
        path: The file to write.
        contents: Its new full text.
    """
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(contents, encoding="utf-8")
    os.replace(tmp, path)


class Command(CustomHelpFormatterMixin, OutMixin, BaseCommand):
    """Write the server's clients file and nginx's key map from the API keys."""

    help = _(
        "[Write the render server's client file and nginx's API-key map from "
        "the site's live API keys. Both are overwritten from scratch on every "
        "run. The server reads its client file at startup and nginx reads its "
        "map on reload, so restart the server and reload nginx afterwards.]"
    )

    def get_short_help(self):
        """Return the memo shown with ``-h``.

        Left untranslated: the argument alignment is layout, which a msgid must
        not carry.

        Returns:
            str: The short help text.
        """
        cmd = Path(__file__).stem
        return (
            f"{cmd} — write the render server's front from the API keys\n"
            "\n"
            "  -d / --dry-run   Print both files instead of writing them\n"
            "\n"
            "  Use --help for full documentation."
        )

    def get_epilog(self):
        """Return the examples shown with ``--help``.

        Left untranslated: the example commands are layout, which a msgid must
        not carry.

        Returns:
            str: The epilog text.
        """
        cmd = Path(__file__).stem
        return (
            "Examples:\n"
            "  # Write both files:\n"
            f"  python manage.py {cmd}\n"
            "\n"
            "  # See what would be written, touching nothing:\n"
            f"  python manage.py {cmd} --dry-run"
        )

    def add_arguments(self, parser):
        """Declare the command's arguments.

        Args:
            parser: The argument parser.
        """
        parser.add_argument(
            "-d",
            "--dry-run",
            action="store_true",
            help=_("[Print both files to stdout instead of writing them.]"),
        )

    def handle(self, *args, **options):
        """Render both files and write them, or print them under ``--dry-run``.

        One query loads the live keys; the two files are rendered from them.

        Args:
            *args: Unused.
            **options: Parsed arguments.
        """
        keys = list(ApiKey.objects.all())
        clients_toml = render_clients_toml(keys, settings.PDF_SERVER_FONT_STORE_DIR)
        nginx_map = render_nginx_map(keys)

        if options["dry_run"]:
            self.out(f"# {settings.PDF_SERVER_CLIENTS_FILE}")
            self.out(clients_toml)
            self.out(f"# {settings.PDF_SERVER_NGINX_MAP_FILE}")
            self.out(nginx_map)
            return

        _write_atomically(settings.PDF_SERVER_CLIENTS_FILE, clients_toml)
        _write_atomically(settings.PDF_SERVER_NGINX_MAP_FILE, nginx_map)
        self.out_success(
            gettext("[Wrote {count} client(s) to {clients} and {nginx}.]").format(
                count=len(keys),
                clients=settings.PDF_SERVER_CLIENTS_FILE,
                nginx=settings.PDF_SERVER_NGINX_MAP_FILE,
            )
        )
