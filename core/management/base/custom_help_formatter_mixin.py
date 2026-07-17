"""Custom help formatter mixin for Django management commands.

Provides custom argparse formatting for Django management commands.

Problem
-------
By default, Django management commands use argparse's standard formatter which:
- Wraps long lines automatically, breaking intentional formatting
- Removes manual indentation in help text
- Collapses multiple newlines into single spaces

Additionally, ``-h`` and ``--help`` are treated as identical aliases,
making it impossible to offer a quick memo vs. full documentation.

Solution
--------
This mixin replaces the default formatter with RawTextHelpFormatter, adds
epilog support, and optionally splits ``-h`` (short summary) from ``--help``
(full documentation).

Usage
-----
1. Import the mixin:

    from myapp.utils.custom_help_formatter_mixin import CustomHelpFormatterMixin

2. Add it BEFORE BaseCommand in your class inheritance (MRO order matters):

    class Command(CustomHelpFormatterMixin, BaseCommand):
        help = "Short description shown in command list."

        epilog = '''
    Examples:
        python manage.py my_command --verbose
        python manage.py my_command --config=prod.json

    Notes:
        - First note here
        - Second note here
        '''

3. Or use dynamic epilog via get_epilog() method:

    class Command(CustomHelpFormatterMixin, BaseCommand):
        help = "Import data from external source."

        def get_epilog(self):
            available_sources = ", ".join(get_available_sources())
            return f'''
    Available sources: {available_sources}

    Examples:
        python manage.py import_data --source=api
        python manage.py import_data --source=csv --file=data.csv
            '''

4. Split -h (memo) from --help (full docs) with short_help:

    class Command(CustomHelpFormatterMixin, BaseCommand):
        help = "Clean GTI/GTR/Coverage fields."

        short_help = '''
    clean_project_fields — Clean GTI/GTR/Coverage

    Quick options:
      -e, --execute    Execute cleaning (default: dry-run)
      --verify         Verify after cleaning

    Use --help for full documentation.
        '''

        epilog = '''
    CONTEXT:
        Project-type proposals should not use GTI/GTR/Coverage...
    ...
        '''

    When short_help is defined:
        -h   → prints short_help text and exits
        --help → prints full argparse help (description + args + epilog) and exits

    When short_help is NOT defined:
        -h / --help → standard argparse behavior (identical output)

Output Example
--------------
Without this mixin:
    $ python manage.py my_command --help
    usage: manage.py my_command [-h]
    Short description. Examples: python manage.py my_command --verbose python...

With this mixin:
    $ python manage.py my_command --help
    usage: manage.py my_command [-h]

    Short description shown in command list.

    Examples:
        python manage.py my_command --verbose
        python manage.py my_command --config=prod.json

    Notes:
        - First note here
        - Second note here

With short_help defined:
    $ python manage.py my_command -h
    clean_project_fields — Clean GTI/GTR/Coverage

    Quick options:
      -e, --execute    Execute cleaning
      --verify         Verify after cleaning

    Use --help for full documentation.

    $ python manage.py my_command --help
    usage: manage.py my_command [-h] [--help] ...
    (full argparse output with all groups and epilog)

Why MRO Order Matters
---------------------
Python's Method Resolution Order (MRO) determines which class's method gets
called first. By placing CustomHelpFormatterMixin BEFORE BaseCommand:

    class Command(CustomHelpFormatterMixin, BaseCommand)

The mixin's create_parser() is called first, which then calls
super().create_parser() to get the original parser from BaseCommand,
and finally applies custom formatting.

Wrong order would skip the mixin entirely:

    class Command(BaseCommand, CustomHelpFormatterMixin)  # WRONG!
"""

import argparse
import logging
import shutil
import sys
import textwrap
from abc import ABC
from argparse import RawTextHelpFormatter

logger = logging.getLogger(__name__)


def _is_decoration_line(line):
    """Return True if ``line`` is a pure-punctuation decoration.

    Detects ASCII heading underlines (``---``, ``===``, ``~~~``, ...) so
    they are not merged into the preceding title when a prose block is
    reflowed.

    Args:
        line: Single line of text.

    Returns:
        True when the line is non-blank and contains no alphanumeric
        character.
    """
    stripped = line.strip()
    return bool(stripped) and not any(c.isalnum() for c in stripped)


def _reflow_blocks(text, width):
    """Reflow prose paragraphs to ``width``, keep structured blocks verbatim.

    The input is walked line by line and grouped into three kinds of blocks:

        * ``blank``     - a single empty line separator
        * ``verbatim``  - any run containing at least one indented line or
                          one decoration line, plus any prose line that
                          directly introduces an indented line (section
                          header like ``Examples:`` or argparse-style term
                          ``-v, --verbosity {0,1,2,3}``)
        * ``prose``     - everything else: consecutive non-indented,
                          non-decoration lines not followed by indent

        Prose blocks are collapsed to a single paragraph and wrapped with
        ``textwrap.fill`` so the output adapts to the terminal width.
        Verbatim blocks are emitted unchanged, preserving the manual layout
        on which indented lists, heading underlines, and code examples rely.

    Args:
        text: Help text, typically already stripped of leading/trailing
            whitespace.
        width: Target column width, usually the current terminal width
            minus a small safety margin.

    Returns:
        Reformatted text with blank-line separation preserved.
    """
    lines = text.splitlines()
    blocks = []
    current_kind = None
    current_lines = []

    def flush():
        nonlocal current_kind, current_lines
        if current_lines:
            blocks.append((current_kind, current_lines))
        current_kind = None
        current_lines = []

    def next_nonblank_is_indented(idx):
        for nxt in lines[idx + 1 :]:
            if not nxt.strip():
                return False
            return nxt.startswith((" ", "\t"))
        return False

    for i, line in enumerate(lines):
        if not line.strip():
            flush()
            blocks.append(("blank", [""]))
            continue
        is_indent = line.startswith((" ", "\t"))
        is_deco = _is_decoration_line(line)
        if is_indent:
            if current_kind != "verbatim":
                flush()
                current_kind = "verbatim"
            current_lines.append(line)
        elif is_deco:
            # Deco attaches to the current block (usually a title).
            current_kind = "verbatim"
            current_lines.append(line)
        elif next_nonblank_is_indented(i):
            # Prose line acting as a header/term for the following list.
            flush()
            current_kind = "verbatim"
            current_lines.append(line)
        else:
            if current_kind == "verbatim":
                flush()
            if current_kind is None:
                current_kind = "prose"
            current_lines.append(line)
    flush()

    output = []
    for kind, lns in blocks:
        if kind == "blank":
            output.append("")
        elif kind == "verbatim":
            output.extend(lns)
        else:
            paragraph = " ".join(ln.strip() for ln in lns)
            output.append(
                textwrap.fill(
                    paragraph,
                    width=width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
    return "\n".join(output)


def _terminal_width():
    """Return the current terminal width with a 2-column safety margin."""
    return shutil.get_terminal_size(fallback=(80, 24)).columns - 2


class _ShortHelpAction(argparse.Action):
    """Display short help summary and exit.

    Used internally by CustomHelpFormatterMixin to handle ``-h``.
    Prints the ``short_help`` text stored on the parser instance.
    """

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        **kwargs,
    ):
        """Initialize short help action."""
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            **kwargs,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        """Print short help and exit."""
        short_help_text = getattr(parser, "_short_help_text", "")
        if short_help_text:
            cleaned = short_help_text.replace("[", "").replace("]", "")
            reflowed = _reflow_blocks(cleaned.strip(), _terminal_width())
            parser._print_message(reflowed + "\n", sys.stdout)
        else:
            parser.print_help(sys.stdout)
        parser.exit()


class _FullHelpAction(argparse.Action):
    """Display full help with epilog and exit.

    Used internally by CustomHelpFormatterMixin to handle ``--help``.
    Falls back to standard ``parser.print_help()`` output.
    """

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        **kwargs,
    ):
        """Initialize full help action."""
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            **kwargs,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        """Print full help and exit."""
        parser.print_help(sys.stdout)
        parser.exit()


class CustomHelpFormatterMixin(ABC):  # noqa: B024
    """Mixin to preserve manual formatting in Django command help text.

    CRITICAL: Place this mixin BEFORE BaseCommand in inheritance:
        class Command(CustomHelpFormatterMixin, BaseCommand)

    This is a mixin class designed to be used with Django's BaseCommand.
    The super() calls resolve to BaseCommand methods via MRO.

    Attributes:
        epilog: Static epilog text displayed after help. Override this
            attribute or the get_epilog() method for dynamic content.
        short_help: Short help summary displayed with ``-h``. When
            defined, ``-h`` shows this memo and ``--help`` shows full
            documentation. Override this attribute or the
            get_short_help() method for dynamic content.

    Example:
        class Command(CustomHelpFormatterMixin, BaseCommand):
            help = "Process uploaded files."

            short_help = '''
        process_files — Process uploaded files

          --all    Process everything
          --id N   Process specific file

        Use --help for full documentation.
            '''

            epilog = '''
        Examples:
            python manage.py process_files --all
            python manage.py process_files --id=123
            '''

            def add_arguments(self, parser):
                parser.add_argument("--all", action="store_true")
                parser.add_argument("--id", type=int)

            def handle(self, *args, **options):
                pass
    """

    epilog = ""
    short_help = ""

    def create_parser(self, prog_name, subcommand, **kwargs):
        """Create parser with custom formatter, epilog, and split help.

        When ``short_help`` is defined (via attribute or get_short_help()),
        disables argparse's default ``-h``/``--help`` and registers:
            - ``-h`` → prints short_help memo and exits
            - ``--help`` → prints full argparse help and exits

        When ``short_help`` is not defined, standard behavior is preserved.

        Args:
            prog_name: Program name.
            subcommand: Subcommand name.
            **kwargs: Additional arguments.

        Returns:
            Configured ArgumentParser instance.
        """
        short_help_content = self.short_help or self.get_short_help()

        if short_help_content:
            kwargs.setdefault("add_help", False)

        class CustomHelpFormatter(RawTextHelpFormatter):
            """Custom formatter preserving text formatting."""

            def _format_text(self, text):
                """Reflow prose paragraphs to the current terminal width.

                Indented blocks, heading underlines, and argparse-style
                term/definition entries are kept verbatim; prose runs are
                collapsed and rewrapped to ``self._width``.

                Args:
                    text: Text to format.

                Returns:
                    Formatted text string.
                """
                if not text:
                    return ""

                cleaned_text = text.replace("[", "").replace("]", "")
                reflowed = _reflow_blocks(cleaned_text.strip(), self._width)
                return "\n" + reflowed + "\n\n"

        parser = super().create_parser(prog_name, subcommand, **kwargs)  # noqa
        parser.formatter_class = CustomHelpFormatter

        if short_help_content:
            parser._short_help_text = short_help_content
            parser.add_argument(
                "-h",
                action=_ShortHelpAction,
                help="Show short help summary and exit.",
            )
            parser.add_argument(
                "--help",
                action=_FullHelpAction,
                help="Show full help with examples and exit.",
            )

        epilog_content = self.epilog or self.get_epilog()
        if epilog_content:
            parser.epilog = epilog_content

        return parser

    def get_epilog(self):  # noqa
        """Return dynamic epilog text.

        Override this method in subclasses to generate epilog content
        dynamically at runtime. Useful when epilog depends on database
        content, configuration, or other runtime values.

        Returns:
            Epilog string, or empty string for no epilog.

        Example:
            def get_epilog(self):
                clients = Client.objects.values_list("code", flat=True)
                return f'''
            Available clients: {", ".join(clients)}

            Examples:
                python manage.py bill_client --client=ACME
                '''
        """
        return ""

    def get_short_help(self):  # noqa
        """Return dynamic short help text.

        Override this method in subclasses to generate short help content
        dynamically at runtime. When this returns a non-empty string,
        ``-h`` displays it as a quick memo and ``--help`` displays full
        documentation.

        Returns:
            Short help string, or empty string for default behavior.

        Example:
            def get_short_help(self):
                return '''
            my_command — Do something useful

              --all    Process everything
              --id N   Process one item

            Use --help for full documentation.
                '''
        """
        return ""
