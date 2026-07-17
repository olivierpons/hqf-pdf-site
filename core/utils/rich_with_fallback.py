"""
ANSI Fallback Implementation for Rich library.

This module provides fallback implementations of Rich library components to ensure
scripts work without external dependencies. If Rich is installed, use it for better
performance and features. If not, fallback classes provide equivalent functionality
using plain ANSI escape codes.

Usage:
    from core.utils.rich_with_fallback import (
        RichConsole,
        RichText,
        RichPanel,
        RichTable,
        rich_escape,
        RICH_AVAILABLE,
    )

    # Use directly - no conditional logic needed
    RichConsole.print("[bold green]Success![/]")
    table = RichTable(title="Results")
    table.add_column("ID")
    table.add_row("1")
    RichConsole.print(table)
"""

import re
import sys

MAX_VALUE_LENGTH = 60
MAX_CELL_LENGTH = 40
MAX_MATCH_VALUE_LENGTH = 80
MIN_COLUMN_WIDTH = 15
MAX_COLUMN_WIDTH = 50

RICH_TO_ANSI_PATTERNS = [
    (r"\[bold red\](.*?)\[/\]", "\033[1m\033[91m\\1\033[0m"),
    (r"\[bold green\](.*?)\[/\]", "\033[1m\033[92m\\1\033[0m"),
    (r"\[bold yellow\](.*?)\[/\]", "\033[1m\033[93m\\1\033[0m"),
    (r"\[bold blue\](.*?)\[/\]", "\033[1m\033[94m\\1\033[0m"),
    (r"\[bold\](.*?)\[/\]", "\033[1m\\1\033[0m"),
    (r"\[red\](.*?)\[/\]", "\033[91m\\1\033[0m"),
    (r"\[green\](.*?)\[/\]", "\033[92m\\1\033[0m"),
    (r"\[yellow\](.*?)\[/\]", "\033[93m\\1\033[0m"),
    (r"\[blue\](.*?)\[/\]", "\033[94m\\1\033[0m"),
    (r"\[cyan\](.*?)\[/\]", "\033[96m\\1\033[0m"),
    (r"\[magenta\](.*?)\[/\]", "\033[95m\\1\033[0m"),
    (r"\[dim\](.*?)\[/\]", "\033[2m\\1\033[0m"),
]


class _Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


_STYLE_MAP = {
    "bold": _Colors.BOLD,
    "dim": _Colors.DIM,
    "red": _Colors.RED,
    "green": _Colors.GREEN,
    "yellow": _Colors.YELLOW,
    "blue": _Colors.BLUE,
    "magenta": _Colors.MAGENTA,
    "cyan": _Colors.CYAN,
    "bold red": f"{_Colors.BOLD}{_Colors.RED}",
    "bold green": f"{_Colors.BOLD}{_Colors.GREEN}",
    "bold yellow": f"{_Colors.BOLD}{_Colors.YELLOW}",
    "bold blue": f"{_Colors.BOLD}{_Colors.BLUE}",
    "bold magenta": f"{_Colors.BOLD}{_Colors.MAGENTA}",
    "bold cyan": f"{_Colors.BOLD}{_Colors.CYAN}",
}


def _strip_rich_markup(text):
    """Remove rich markup tags from text, keeping array indices like [0]."""
    text = re.sub(r"\[/]", "", str(text))
    text = re.sub(r"\[/?[a-zA-Z][^]]*]", "", text)
    return text


def _strip_ansi(text):
    """Remove ANSI codes from text for length calculation."""
    return re.sub(r"\033\[[0-9;]*m", "", str(text))


def _apply_style(text, style):
    """Apply ANSI style to text."""
    if not style:
        return text
    color = _STYLE_MAP.get(style.lower(), "")
    if color:
        return f"{color}{text}{_Colors.RESET}"
    return text


class ANSIFallbackText:
    """Fake rich.text.Text class using ANSI codes."""

    def __init__(self, text="", style=""):
        self._parts = []
        if text:
            self._parts.append((str(text), style))

    def append(self, text, style=""):
        self._parts.append((str(text), style))

    def __str__(self):
        result = []
        for text, style in self._parts:
            result.append(_apply_style(text, style))
        return "".join(result)


class ANSIFallbackPanel:
    """Fake rich.panel.Panel class using ANSI box drawing."""

    def __init__(self, content, title="", border_style="", **_kwargs):
        # Absorb rich-only kwargs (expand, padding, box, ...) so callers can write
        # self.Panel(content, expand=False) without crashing under --no-rich; the ANSI
        # fallback has no notion of those.
        self.content = content
        self.title = _strip_rich_markup(title)
        self.border_style = border_style

    def __str__(self):
        content_str = str(self.content)
        content_str = _strip_rich_markup(content_str)
        lines = content_str.split("\n")

        max_len = max(len(_strip_ansi(line)) for line in lines) if lines else 0
        if self.title:
            max_len = max(max_len, len(self.title) + 4)
        width = max_len + 4

        border_color = _STYLE_MAP.get(self.border_style, "")
        reset = _Colors.RESET if border_color else ""

        result = []

        if self.title:
            top_line = (
                f"{border_color}╭─ {_Colors.BOLD}{self.title}{reset}"
                f"{border_color} " + "─" * (width - len(self.title) - 5) + f"╮{reset}"
            )
        else:
            top_line = f"{border_color}╭" + "─" * (width - 2) + f"╮{reset}"
        result.append(top_line)

        for line in lines:
            clean_line = _strip_ansi(line)
            padding = width - len(clean_line) - 4
            result.append(
                f"{border_color}│{reset} {line}{' ' * padding} "
                f"{border_color}│{reset}"
            )

        result.append(f"{border_color}╰" + "─" * (width - 2) + f"╯{reset}")
        return "\n".join(result)


class ANSIFallbackTable:
    """Fake rich.table.Table class using ANSI box drawing."""

    def __init__(
        self,
        title="",
        show_header=True,
        header_style="",
        border_style="",
        **_kwargs,
    ):
        self.title = _strip_rich_markup(title)
        self.show_header = show_header
        self.header_style = header_style
        self.border_style = border_style
        self._columns = []
        self._rows = []

    def add_column(self, header, style="", *, ratio=1, **_kwargs):
        self._columns.append(
            {
                "header": header,
                "style": style,
                "ratio": ratio,
            }
        )

    def add_row(self, *cells, **_kwargs):
        # Symmetric with add_column above: absorb rich-only kwargs (style, end_section,
        # ...) so callers can keep one signature for both Rich and ANSI fallback
        # rendering paths.
        self._rows.append(list(cells))

    def __str__(self):
        if not self._columns:
            return ""

        col_widths = []
        for i, col in enumerate(self._columns):
            max_w = len(col["header"])
            for row in self._rows:
                if i < len(row):
                    cell = _strip_rich_markup(str(row[i]) if row[i] else "")
                    max_w = max(max_w, len(cell))
            min_width = int(col["ratio"] * MIN_COLUMN_WIDTH)
            col_widths.append(max(min(max_w, MAX_COLUMN_WIDTH), min_width))

        border_color = _STYLE_MAP.get(self.border_style, "")
        header_color = _STYLE_MAP.get(self.header_style, "")
        reset = _Colors.RESET if border_color or header_color else ""

        result = []
        total_width = sum(col_widths) + len(self._columns) * 3 + 1

        if self.title:
            result.append(f"\n{border_color}{_Colors.BOLD}{self.title}{reset}")
            result.append(f"{border_color}" + "─" * total_width + f"{reset}")

        if self.show_header:
            header_line = f"{border_color}│{reset}"
            for i, col in enumerate(self._columns):
                header_text = col["header"]
                header_line += (
                    f" {header_color}{_Colors.BOLD}"
                    f"{header_text:<{col_widths[i]}}"
                    f"{reset} {border_color}│{reset}"
                )
            result.append(header_line)
            result.append(
                f"{border_color}├"
                + "┼".join("─" * (w + 2) for w in col_widths)
                + f"┤{reset}"
            )

        for row in self._rows:
            row_line = f"{border_color}│{reset}"
            for i, col in enumerate(self._columns):
                cell = str(row[i]) if i < len(row) and row[i] is not None else ""
                cell = _strip_rich_markup(cell)
                if len(cell) > col_widths[i]:
                    cell = cell[: col_widths[i] - 3] + "..."
                col_style = _STYLE_MAP.get(col["style"], "")
                row_line += (
                    f" {col_style}{cell:<{col_widths[i]}}{reset} "
                    f"{border_color}│{reset}"
                )
            result.append(row_line)

        result.append(
            f"{border_color}╰"
            + "┴".join("─" * (w + 2) for w in col_widths)
            + f"╯{reset}"
        )
        return "\n".join(result)


class ANSIFallbackConsole:
    """Fake rich.console.Console class using print."""

    def __init__(self):
        pass

    def print(self, *args, **_kwargs):
        for arg in args:
            text = str(arg)
            text = self._convert_markup(text)
            print(text)

    @staticmethod
    def _convert_markup(text):
        result = str(text)
        for pattern, replacement in RICH_TO_ANSI_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.DOTALL)

        result = re.sub(r"\[/]", "", result)
        result = re.sub(r"\[/?[a-zA-Z][^]]*]", "", result)
        return result


def _ansi_escape(text):
    """Escape text for safe display (no-op for ANSI fallback)."""
    return str(text)


def _ansi_track(iterable, description=None, total=None):
    """Iterate ``iterable`` while rendering a one-line ANSI progress bar.

    Mimics ``rich.progress.track`` with a minimal feature set when Rich is not
    available. Writes carriage-return + bar to ``sys.stderr`` so the surrounding
    ``print`` lines (typically stdout) are not disturbed.

    Args:
        iterable: Sequence or iterator to walk; ``total`` is required
            when the iterable has no ``__len__``.
        description: Optional prefix label.
        total: Total step count; inferred from ``len(iterable)`` when
            not provided.
    """
    label = description or ""
    if total is None:
        try:
            total = len(iterable)
        except TypeError:
            total = 0
    width = 30
    step = 0

    def _render():
        if total > 0:
            filled = int(width * step / total)
            bar = "#" * filled + "-" * (width - filled)
            percent = 100 * step / total
            line = f"\r{label} [{bar}] {step}/{total} ({percent:5.1f}%)"
        else:
            line = f"\r{label} [{step} items]"
        sys.stderr.write(line)
        sys.stderr.flush()

    _render()
    for item in iterable:
        yield item
        step += 1
        _render()
    sys.stderr.write("\n")
    sys.stderr.flush()


try:
    from rich.console import Console as _RichConsoleClass
    from rich.markup import escape as _rich_escape_func
    from rich.panel import Panel as _RichPanelClass
    from rich.progress import track as _rich_track_func
    from rich.table import Table as _RichTableClass
    from rich.text import Text as _RichTextClass

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    _RichConsoleClass = None
    _rich_escape_func = None
    _RichPanelClass = None
    _rich_track_func = None
    _RichTableClass = None
    _RichTextClass = None

if RICH_AVAILABLE:
    RichConsole = _RichConsoleClass
    RichText = _RichTextClass
    RichPanel = _RichPanelClass
    RichTable = _RichTableClass
    rich_escape = _rich_escape_func
    rich_track = _rich_track_func
else:
    RichConsole = ANSIFallbackConsole
    RichText = ANSIFallbackText
    RichPanel = ANSIFallbackPanel
    RichTable = ANSIFallbackTable
    rich_escape = _ansi_escape
    rich_track = _ansi_track

# Fallback versions always available for forced ANSI mode
FallbackConsole = ANSIFallbackConsole
FallbackText = ANSIFallbackText
FallbackPanel = ANSIFallbackPanel
FallbackTable = ANSIFallbackTable
fallback_escape = _ansi_escape
fallback_track = _ansi_track
