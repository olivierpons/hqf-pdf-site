"""``rewrap_comments`` — re-flow narrow comment blocks at the project width.

The project standard is 88 characters per line (Black's default). Many existing files
have comments wrapped at 60–75 chars instead, which makes long blocks of explanation
visually noisier than they should be. This command walks Python files, finds blocks of
consecutive ``#``-prefixed lines at the same indent, joins their content into a single
string and re-wraps it at the target width.

Scope is intentionally narrow:

* Only ``#``-prefixed standalone comment blocks. Inline comments after code (``x = 1  #
  ...``) are never touched.
* Bullet items (``*``, ``-``, ``+``, ``1.``, ``2)``) are detected and never merged into
  prose.
* Shebangs, encoding lines, separator decorations and tooling pragmas (noqa, type:,
  fmt:, pragma:, pylint:, isort:) are left alone.
* Real docstrings (AST-detected) have their prose paragraphs re-flowed too. Google
  section headers (``Args:``…), bullet lists (including ones indented deeper than the
  quote), Markdown blockquotes and underline decorations are each kept on their own
  block; ``Args:`` bodies stay verbatim.

What this command **does not** do:

* Implicit-concat string literals (``_("foo " "bar " "baz")``) — AST-detecting these
  safely did not survive contact with Black; re-flow them by hand.

Examples:
  # Default — comments only, in-place, on the project app dirs.
  python manage.py rewrap_comments

  # Dry run on a single file.
  python manage.py rewrap_comments --dry-run app/utils/email.py

  # CI mode — exit 1 if anything would change.
  python manage.py rewrap_comments --check
"""

# Vendored reflow tool: the walkers below are text state machines by nature, so their
# local, branch and statement counts run past the defaults; splitting them would scatter
# one algorithm across many functions.
# pylint: disable=too-many-locals,too-many-branches,too-many-statements

from __future__ import annotations

import ast
import difflib
import re
import textwrap
from argparse import ArgumentParser
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext_lazy as _

from core.management.base.custom_help_formatter_mixin import (
    CustomHelpFormatterMixin,
)
from core.management.base.out_mixin import OutMixin

# Comment bodies matching any of these patterns are decorative or tool-readable
# directives — never re-flow them.
_PRAGMA_PREFIXES: tuple[str, ...] = (
    "noqa",
    "type:",
    "type :",
    "fmt:",
    "pragma:",
    "pylint:",
    "isort:",
)
_SEPARATOR_REGEX = re.compile(r"^[\-=*#_~+]{10,}$")
# Editor folding markers (``# region Foo`` / ``# endregion``). PyCharm and VS Code read
# them as structure, not prose: merging one into the paragraph below it silently deletes
# a fold. ``endregion`` takes no argument; ``region`` takes an optional label.
_FOLD_MARKER_REGEX = re.compile(r"^(?:region\b.*|endregion\s*)$", re.IGNORECASE)
# Docstring section underlines (RST / Markdown setext titles) are usually as long as the
# title above — often 5-9 chars, below the comment-block separator threshold. Match any
# single punctuation character repeated 3+ times so short underlines like ``---``,
# ``===``, ``~~~`` after a heading text line are recognized and kept on their own line
# instead of being merged with the title.
_DOCSTRING_SEPARATOR_REGEX = re.compile(r"^([\-=*~_+])\1{2,}$")
_SHEBANG_REGEX = re.compile(r"^#!\S")
_ENCODING_REGEX = re.compile(r"^#\s*-\*-\s+coding")
# Bullet markers — every match starts a fresh paragraph. Without this the rewrapper
# merges sibling bullets into one prose line.
_BULLET_REGEX = re.compile(r"^(\*|-|\+|\d+[.)]|[a-zA-Z][.)])\s+\S")
# Google-style docstring section headers — always start a fresh paragraph, even when no
# blank line separates them from the previous paragraph.
_DOCSTRING_SECTION_HEADER = re.compile(
    r"^(Args|Arguments|Returns|Yields|Raises|Example|Examples|Note|Notes|"
    r"Attributes|See Also|Warns|Warning|Warnings|References|Todo)s?:\s*$"
)
# Comment line: leading whitespace + ``#`` + body.
_COMMENT_LINE_REGEX = re.compile(r"^(?P<indent>\s*)#(?P<body>.*)$")
# Matches a comment body that is commented-out code rather than prose. When any body in
# a block matches, the block is emitted verbatim (one source line each) instead of
# joined and re-flowed, so a commented-out dict / list / call keeps its layout.
# Alternatives, in order: a line ending with an opening bracket; a line that is only
# closing brackets with an optional trailing comma; a dict-literal key ``'foo':`` /
# ``"foo":``; an assignment ``foo =`` / ``foo.bar =``; a single non-space token followed
# by a comma (list / enum / tuple item, e.g. ``"a.b.c",``, ``42,``, ``FOO_BAR,``). A
# multi-word line ending in a comma is prose and is left for the normal re-flow path.
_LIKELY_CODE_BODY = re.compile(
    r"^(?:"
    r".*[{\[(]\s*$"
    r"|\s*[)\]}](?:\s*,)?\s*$"
    r"|\s*['\"][\w.\-]+['\"]\s*:"
    r"|\s*[\w.]+\s*="
    r"|\s*\S+,\s*$"
    r")"
)
# Matches a Markdown blockquote line: one or more ``>`` markers followed by content.
# Captures the marker run (``>``, ``>>``, ``>>>`` for nested quotes) and the body, so a
# multi-line blockquote is re-flowed under its marker instead of having the inner ``>``
# joined into the prose.
_QUOTE_LINE_REGEX = re.compile(r"^(?P<marker>>+)\s?(?P<body>.*)$")


def _is_unmergeable_body(body: str) -> bool:
    """Return ``True`` when a single comment body must not be re-flowed."""
    stripped = body.strip()
    if not stripped:
        return True
    if _SEPARATOR_REGEX.match(stripped):
        return True
    if _FOLD_MARKER_REGEX.match(stripped):
        return True
    if _SHEBANG_REGEX.match("#" + body):
        return True
    if _ENCODING_REGEX.match("#" + body):
        return True
    lower = stripped.lower()
    return any(lower.startswith(p) for p in _PRAGMA_PREFIXES)


def _ends_on_a_split_word(paragraph: str) -> bool:
    """Return whether ``paragraph`` ends on a word an earlier wrap cut in two.

    The signal is a hyphen welded to the end of a word — ``"authorised-"``. A hyphen
    standing alone after a space is a dash or a minus sign (``"date_start -"``, ``"one
    clause --"``), and whatever follows it starts a new word.

    Args:
        paragraph: The text accumulated so far.

    Returns:
        ``True`` when the next body continues the last word.
    """
    return len(paragraph) >= 2 and paragraph.endswith("-") and paragraph[-2].isalnum()


def join_bodies(bodies: Iterable[str]) -> str:
    """Join comment bodies into one paragraph, healing hyphen-split words.

    A body ending on a welded hyphen carries a word an earlier wrap cut in two
    (``"authorised-"`` then ``"redirect-URI list"``). Joining those on a space leaves
    the split inside the word — ``"authorised- redirect-URI"`` — so the two fragments
    are glued back together instead. Every other pair of bodies is joined on a single
    space.

    Args:
        bodies: The comment bodies of one block, in source order.

    Returns:
        The paragraph to re-wrap.
    """
    paragraph = ""
    for body in bodies:
        piece = body.strip()
        if not piece:
            continue
        if not paragraph:
            paragraph = piece
        elif _ends_on_a_split_word(paragraph) and piece[:1].isalnum():
            paragraph += piece
        else:
            paragraph += f" {piece}"
    return paragraph.strip()


def _strip_one_leading_space(body: str) -> str:
    """Drop the conventional single space after ``#`` if present."""
    if body.startswith(" "):
        return body[1:]
    return body


class Command(CustomHelpFormatterMixin, OutMixin, BaseCommand):
    help = str(_("[Re-flow narrow comment blocks at the project line width.]"))
    short_help = str(
        _(
            "[Rewrap comment blocks to project width. "
            "Use --help for full documentation.]"
        )
    )
    epilog = str(
        _(
            "[Walks the given paths, finds consecutive ``#``-comment "
            "blocks at the same indent and rewraps each block to the "
            "target width. Bullets and numbered list items each stay "
            "on their own line. Skips shebangs, encoding lines, "
            "separator decorations and tooling pragmas (noqa, type:, "
            "fmt:, pragma:, pylint:, isort:). Idempotent and "
            "Black-stable.]"
        )
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "paths",
            nargs="*",
            type=str,
            help=str(
                _(
                    "[Files or directories. Defaults to the project "
                    "app dirs (app, core, websearch).]"
                )
            ),
        )
        parser.add_argument(
            "--width",
            type=int,
            default=88,
            help=str(_("[Target maximum line width. Default: 88.]")),
        )
        parser.add_argument(
            "--break-on-hyphens",
            action="store_true",
            default=False,
            help=str(
                _(
                    "[Allow line breaks at hyphens inside hyphenated "
                    "words. Off by default.]"
                )
            ),
        )
        parser.add_argument(
            "--exclude",
            action="append",
            default=[],
            help=str(
                _(
                    "[Substring filter. Any path containing this "
                    "substring is skipped. Repeatable.]"
                )
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=str(
                _(
                    "[Do not write changes; print a unified diff of "
                    "what would change.]"
                )
            ),
        )
        parser.add_argument(
            "--check",
            action="store_true",
            default=False,
            help=str(
                _(
                    "[Exit code 1 if any file would change. Implies "
                    "--dry-run. Useful for CI.]"
                )
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        self.set_verbosity(int(options.get("verbosity", 1)))
        width: int = int(options["width"])
        break_on_hyphens: bool = bool(options["break_on_hyphens"])
        exclude: list[str] = list(options.get("exclude") or [])
        dry_run: bool = bool(options["dry_run"]) or bool(options["check"])
        check_mode: bool = bool(options["check"])
        paths: list[str] = options["paths"] or self._default_paths()

        files = self._collect_python_files(paths, exclude=exclude)
        if not files:
            raise CommandError(str(_("[No Python files matched the given paths.]")))

        changed = 0
        total = len(files)
        for path in files:
            original = path.read_text(encoding="utf-8")
            rewritten = self._rewrap(
                original, width=width, break_on_hyphens=break_on_hyphens
            )
            if rewritten == original:
                self.out(f"  unchanged: {path}", min_verbosity=2)
                continue
            changed += 1
            if dry_run:
                self._print_diff(path, original, rewritten)
            else:
                path.write_text(rewritten, encoding="utf-8")
                self.out(f"  rewrapped: {path}", min_verbosity=1)

        verb = "would change" if dry_run else "changed"
        self.out_success(f"Done. {changed}/{total} file(s) {verb}.", min_verbosity=1)
        if check_mode and changed:
            raise CommandError(str(_("[--check: comment blocks need rewrapping.]")))

    @staticmethod
    def _default_paths() -> list[str]:
        """Return the local-app paths to walk by default.

        Reads ``INSTALLED_APPS`` via Django's app registry and keeps every app whose
        on-disk path is under ``settings.BASE_DIR`` (i.e. project-owned apps).
        Third-party apps (``django.*``, ``allauth.*``, ``rest_framework.*``,
        ``modeltranslation.*``, etc.) live under ``site-packages`` outside ``BASE_DIR``
        and are filtered out automatically — no hardcoded list to keep in sync.
        """
        base = Path(getattr(settings, "BASE_DIR", Path.cwd())).resolve()
        seen: set[Path] = set()
        out: list[str] = []
        for app_config in django_apps.get_app_configs():
            try:
                app_path = Path(app_config.path).resolve()
            except TypeError, ValueError:
                continue
            try:
                app_path.relative_to(base)
            except ValueError:
                # Not under BASE_DIR — third-party, skip.
                continue
            if app_path in seen:
                continue
            seen.add(app_path)
            out.append(
                str(app_path.relative_to(base)) if app_path != base else str(app_path)
            )
        return out

    @staticmethod
    def _collect_python_files(paths: list[str], *, exclude: list[str]) -> list[Path]:
        """Resolve ``paths`` to a list of ``*.py`` files."""
        out: list[Path] = []
        for raw in paths:
            p = Path(raw)
            if p.is_file() and p.suffix == ".py":
                out.append(p)
                continue
            if p.is_dir():
                out.extend(sorted(p.rglob("*.py")))
        if not exclude:
            return out
        return [p for p in out if not any(s in str(p) for s in exclude)]

    def _rewrap(
        self, source: str, *, width: int, break_on_hyphens: bool = False
    ) -> str:
        """Apply rewrapping to a whole file's text."""
        lines = source.splitlines(keepends=True)
        docstring_lineset = self._docstring_line_set(source)
        out_lines = self._rewrap_comment_blocks(
            lines,
            width=width,
            break_on_hyphens=break_on_hyphens,
            docstring_lineset=docstring_lineset,
        )
        out_lines = self._rewrap_docstrings(
            "".join(out_lines), width=width, break_on_hyphens=break_on_hyphens
        )
        return "".join(out_lines)

    @classmethod
    def _docstring_line_set(cls, source: str) -> frozenset[int]:
        """Return every 0-indexed line number that sits inside a real docstring.

        Built from :meth:`_docstring_ranges` (1-indexed inclusive) so the comment-block
        pass can ``if i in docstring_lineset: skip`` cheaply. RST enumerated bullets
        like ``#.`` inside a docstring otherwise look like Python comments to
        :data:`_COMMENT_LINE_REGEX` and get re-flowed into the surrounding prose,
        producing artefacts such as ``# . X-Real-IP`` (a space-separated split of the
        original bullet marker).
        """
        ranges = cls._docstring_ranges(source)
        lineset: set[int] = set()
        for start, end in ranges:
            for ln in range(start - 1, end):
                lineset.add(ln)
        return frozenset(lineset)

    def _rewrap_comment_blocks(
        self,
        lines: list[str],
        *,
        width: int,
        break_on_hyphens: bool = False,
        docstring_lineset: frozenset[int] | None = None,
    ) -> list[str]:
        """Re-flow every standalone-comment block.

        Lines inside a docstring (per ``docstring_lineset``, 0-indexed) are emitted
        verbatim — the docstring pass downstream is the only one allowed to touch them.
        Without this guard a line like ``    #. ``X-Real-IP``...`` inside a docstring is
        misread as a Python comment and reformatted.
        """
        out: list[str] = []
        skip = docstring_lineset or frozenset()
        i = 0
        n = len(lines)
        while i < n:
            if i in skip:
                out.append(lines[i])
                i += 1
                continue
            line = lines[i]
            block = self._gather_comment_block(lines, i)
            if block is None:
                out.append(line)
                i += 1
                continue
            indent, bodies, end = block
            if any(idx in skip for idx in range(i, end)):
                out.append(lines[i])
                i += 1
                continue
            if any(_LIKELY_CODE_BODY.search(b) for b in bodies):
                # Commented-out code block (``# "key": value,`` lines, dict / list
                # literals, ``LOGGING = { ... }`` snippets). Joining those bodies as
                # prose destroys their structure — emit each source line verbatim. The
                # structural-token heuristic in :data:`_LIKELY_CODE_BODY` flags lines
                # that end with ``,``, ``{``, ``[``, ``(``, lines made entirely of
                # closing brackets optionally followed by a comma, dict-literal keys and
                # assignments.
                for j in range(i, end):
                    out.append(lines[j])
                i = end
                continue
            quote_marker = self._uniform_quote_marker(bodies)
            if quote_marker is not None:
                # A block whose every body shares one ``>`` run is a Markdown
                # blockquote. Strip the marker from each body, join the contents,
                # re-wrap, and re-emit each output line as ``# > <wrapped>`` so the
                # quote stays a quote at the project width.
                stripped_bodies: list[str] = []
                for b in bodies:
                    qm = _QUOTE_LINE_REGEX.match(b.strip())
                    stripped_bodies.append(
                        qm.group("body").strip() if qm is not None else b.strip()
                    )
                joined = join_bodies(stripped_bodies)
                inner_prefix = f"{quote_marker} "
                wrapped = textwrap.fill(
                    joined,
                    width=max(width - len(indent) - 2 - len(inner_prefix), 20),
                    break_long_words=False,
                    break_on_hyphens=break_on_hyphens,
                )
                for w in wrapped.splitlines():
                    out.append(f"{indent}# {inner_prefix}{w}\n")
                i = end
                continue
            joined = join_bodies(bodies)
            wrapped = textwrap.fill(
                joined,
                width=max(width - len(indent) - 2, 20),
                break_long_words=False,
                break_on_hyphens=break_on_hyphens,
            )
            for w in wrapped.splitlines():
                out.append(f"{indent}# {w}\n")
            i = end
        return out

    @staticmethod
    def _uniform_quote_marker(bodies: list[str]) -> str | None:
        """Return the shared ``>`` run when every body starts with one.

        ``> ``, ``>> ``, ``>>> `` are valid Markdown blockquote nesting levels. The
        block is re-flowed only when every body shares the same marker; a mix of markers
        is a nested quote and is returned as ``None`` (left unchanged).
        """
        if not bodies:
            return None
        markers: set[str] = set()
        for body in bodies:
            match = _QUOTE_LINE_REGEX.match(body.strip())
            if match is None:
                return None
            markers.add(match.group("marker"))
        if len(markers) != 1:
            return None
        return next(iter(markers))

    @staticmethod
    def _gather_comment_block(
        lines: list[str], start: int
    ) -> tuple[str, list[str], int] | None:
        """Identify a mergeable comment block starting at ``start``.

        Returns ``(indent, bodies, end_index)`` for any block of one or more
        comment-only lines at the same indent. Single-line blocks are returned too — the
        caller re-wraps them only if they exceed the target width. Bullet lines are
        *each* their own one-line block, never merged with siblings.
        """
        first = lines[start]
        first_text = first[:-1] if first.endswith("\n") else first
        m = _COMMENT_LINE_REGEX.match(first_text)
        if m is None:
            return None
        indent = m.group("indent")
        body = m.group("body")
        if _is_unmergeable_body(body):
            return None

        first_clean = _strip_one_leading_space(body)
        # Bullets are paragraph boundaries — start a 1-line block.
        if _BULLET_REGEX.match(first_clean):
            return indent, [first_clean], start + 1

        bodies: list[str] = [first_clean]
        end = start + 1
        while end < len(lines):
            cand = lines[end]
            cand_text = cand[:-1] if cand.endswith("\n") else cand
            cm = _COMMENT_LINE_REGEX.match(cand_text)
            if cm is None:
                break
            if cm.group("indent") != indent:
                break
            cb = cm.group("body")
            if _is_unmergeable_body(cb):
                break
            cb_clean = _strip_one_leading_space(cb)
            # A bullet in the middle of a block ends the current block — it will start
            # its own one-line block on the next iteration.
            if _BULLET_REGEX.match(cb_clean):
                break
            bodies.append(cb_clean)
            end += 1
        return indent, bodies, end

    # ---- Docstrings (AST-detected) -----------------------------------

    @staticmethod
    def _docstring_ranges(source: str) -> list[tuple[int, int]]:
        """Return ``[(start_line, end_line)]`` (1-indexed, inclusive).

        AST-based: a docstring is the first statement of a Module, FunctionDef,
        AsyncFunctionDef or ClassDef body, and is a bare ``str`` constant. Triple-quoted
        strings used as data — HTML fixtures, raw blobs assigned to variables — are NOT
        in this list and the rewrapper never touches them.
        """
        ranges: list[tuple[int, int]] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ranges

        def collect(body: list[ast.stmt]) -> None:
            if not body:
                return
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                start = first.lineno
                end = getattr(first, "end_lineno", start) or start
                ranges.append((start, end))

        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                collect(node.body)
        return ranges

    def _rewrap_docstrings(
        self, source: str, *, width: int, break_on_hyphens: bool = False
    ) -> list[str]:
        """Re-flow paragraphs in every real docstring.

        AST-based detection so triple-quoted data strings stay intact. Each docstring's
        body is split at blank lines into paragraphs; lines indented past the
        docstring's base indent are preserved verbatim (Google-style ``Args:`` blocks).
        Bullets and section headers (``Args:``, ``Returns:`` etc.) each start their own
        paragraph.
        """
        ranges = self._docstring_ranges(source)
        lines = source.splitlines(keepends=True)
        if not ranges:
            return lines

        # ranges are 1-indexed inclusive; convert to 0-indexed ``[start,
        # end_exclusive)`` so we can slice ``lines``.
        slots = sorted((start - 1, end) for start, end in ranges)

        out: list[str] = []
        i = 0
        n = len(lines)
        slot_iter = iter(slots)
        next_slot = next(slot_iter, None)

        while i < n:
            if next_slot is None or i < next_slot[0]:
                out.append(lines[i])
                i += 1
                continue
            start, end_excl = next_slot
            block = lines[start:end_excl]
            rewrapped = self._rewrap_one_docstring_block(
                block, width=width, break_on_hyphens=break_on_hyphens
            )
            out.extend(rewrapped)
            i = end_excl
            next_slot = next(slot_iter, None)
        return out

    @staticmethod
    def _rewrap_one_docstring_block(
        block: list[str], *, width: int, break_on_hyphens: bool = False
    ) -> list[str]:
        """Re-flow paragraphs inside one docstring.

        ``block`` is the slice of ``lines`` from the opening triple- quote to the
        closing triple-quote, both inclusive. Single-line docstrings (open + close on
        the same line) are returned untouched.
        """
        if not block:
            return block
        opening = block[0]
        # Detect single-line docstring (open and close on same line).
        m = re.match(r'^(?P<indent>\s*)("""|\'\'\')', opening.rstrip("\n"))
        if m is None:
            return block
        quote = m.group(2)
        indent = m.group("indent")
        rest_of_first = opening.rstrip("\n")[len(indent) + 3 :]
        if quote in rest_of_first:
            # Single-line — leave alone.
            return block

        if len(block) < 2:
            return block

        # The closing line is the last one (it contains ``quote``).
        closing = block[-1]
        body_lines = block[1:-1]

        out: list[str] = [opening]
        buf: list[str] = []
        base_indent = indent

        def flush() -> None:
            if not buf:
                return
            paragraph = join_bodies(buf)
            if not paragraph:
                buf.clear()
                return
            paragraph_wrapped = textwrap.fill(
                paragraph,
                width=max(width - len(base_indent), 20),
                break_long_words=False,
                break_on_hyphens=break_on_hyphens,
            )
            for w in paragraph_wrapped.splitlines():
                out.append(f"{base_indent}{w}\n")
            buf.clear()

        i = 0
        n = len(body_lines)
        while i < n:
            raw = body_lines[i]
            text = raw.rstrip("\n")
            if text.strip() == "":
                flush()
                out.append(raw)
                i += 1
                continue
            line_indent_len = len(text) - len(text.lstrip())
            if line_indent_len != len(base_indent):
                stripped_deep = text.strip()
                if _BULLET_REGEX.match(stripped_deep):
                    # An indented bullet list (common: a ``*``/``-`` enumeration nested
                    # under a sentence, sitting deeper than the docstring quote indent).
                    # Without this branch the whole list fell through to the verbatim
                    # path below and kept whatever narrow hand-wrapping it had. Re-flow
                    # it to the project width using the bullet's own indent, one item
                    # per block with a hanging indent — same contract as the base-indent
                    # bullet branch.
                    flush()
                    bullet_indent = " " * line_indent_len
                    bullet_text_lines = [stripped_deep]
                    j = i + 1
                    while j < n:
                        cand = body_lines[j].rstrip("\n")
                        if cand.strip() == "":
                            break
                        cand_indent_len = len(cand) - len(cand.lstrip())
                        # Strictly deeper than the bullet line = continuation of this
                        # item; a sibling bullet or any shallower line ends it.
                        if cand_indent_len <= line_indent_len:
                            break
                        bullet_text_lines.append(cand.strip())
                        j += 1
                    marker_match = re.match(r"^(\S+)\s+", stripped_deep)
                    marker = marker_match.group(1) + " " if marker_match else "- "
                    first_body = stripped_deep[len(marker) :]
                    joined = join_bodies([first_body, *bullet_text_lines[1:]])
                    wrapped = textwrap.fill(
                        joined,
                        width=max(width, 20),
                        initial_indent=bullet_indent + marker,
                        subsequent_indent=bullet_indent + " " * len(marker),
                        break_long_words=False,
                        break_on_hyphens=break_on_hyphens,
                    )
                    for w in wrapped.splitlines():
                        out.append(w + "\n")
                    i = j
                    continue
                # More-indented than base — could be an Args block body (``a: ...``) we
                # leave verbatim. Bullet continuations are gathered by the bullet branch
                # below from a base-indent bullet line, so this branch never sees them
                # under normal flow.
                flush()
                out.append(raw)
                i += 1
                continue
            stripped = text.strip()
            if _DOCSTRING_SECTION_HEADER.match(stripped):
                flush()
                out.append(raw)
                i += 1
                continue
            if _SEPARATOR_REGEX.match(stripped) or _DOCSTRING_SEPARATOR_REGEX.match(
                stripped
            ):
                # Decoration line — RST/Markdown header underlines made of ``-``, ``=``,
                # ``*`` etc. Two regexes: the long-separator one (10+ chars, also used
                # for ``#`` comments) and the docstring- specific one that catches short
                # underlines (3+ chars of the same punctuation, e.g. ``-------`` under a
                # 7-character title like ``Problem``). Without this branch the underline
                # was merged into the buffered paragraph and the rendered output became
                # ``Problem -------`` on a single line.
                flush()
                out.append(raw)
                i += 1
                continue
            quote_match = _QUOTE_LINE_REGEX.match(stripped)
            if quote_match is not None:
                # Markdown blockquote run. Strip the ``>``-prefix from every consecutive
                # line at the same base indent, join the bodies into a single paragraph,
                # re-wrap at the target width, then re-apply ``> `` (single space) on
                # every output line. Without this branch the inner ``>`` markers leak
                # into the joined text and re-emerge mid-line as garbage.
                flush()
                marker = quote_match.group("marker")
                quote_bodies = [quote_match.group("body").strip()]
                j = i + 1
                while j < n:
                    cand = body_lines[j].rstrip("\n")
                    if cand.strip() == "":
                        break
                    cand_indent_len = len(cand) - len(cand.lstrip())
                    if cand_indent_len != len(base_indent):
                        break
                    cand_match = _QUOTE_LINE_REGEX.match(cand.strip())
                    if cand_match is None:
                        break
                    if cand_match.group("marker") != marker:
                        break
                    quote_bodies.append(cand_match.group("body").strip())
                    j += 1
                joined_quote = join_bodies(quote_bodies)
                quote_prefix = f"{marker} "
                quote_wrapped = textwrap.fill(
                    joined_quote,
                    width=max(width - len(base_indent) - len(quote_prefix), 20),
                    break_long_words=False,
                    break_on_hyphens=break_on_hyphens,
                )
                for w in quote_wrapped.splitlines():
                    out.append(f"{base_indent}{quote_prefix}{w}\n")
                i = j
                continue
            if _BULLET_REGEX.match(stripped):
                # Gather the bullet block: the bullet line + every following line at
                # deeper indent. Lines at base indent (siblings, prose) and blank lines
                # end it.
                flush()
                bullet_text_lines = [stripped]
                j = i + 1
                while j < n:
                    cand = body_lines[j].rstrip("\n")
                    if cand.strip() == "":
                        break
                    cand_indent_len = len(cand) - len(cand.lstrip())
                    if cand_indent_len <= len(base_indent):
                        break
                    bullet_text_lines.append(cand.strip())
                    j += 1
                marker_match = re.match(r"^(\S+)\s+", stripped)
                marker = marker_match.group(1) + " " if marker_match else "- "
                first_body = stripped[len(marker) :]
                joined = join_bodies([first_body, *bullet_text_lines[1:]])
                hang_prefix = base_indent + " " * len(marker)
                initial_prefix = base_indent + marker
                wrapped = textwrap.fill(
                    joined,
                    width=max(width, 20),
                    initial_indent=initial_prefix,
                    subsequent_indent=hang_prefix,
                    break_long_words=False,
                    break_on_hyphens=break_on_hyphens,
                )
                for w in wrapped.splitlines():
                    out.append(w + "\n")
                i = j
                continue
            buf.append(text)
            i += 1
        flush()
        out.append(closing)
        return out

    def _print_diff(self, path: Path, before: str, after: str) -> None:
        diff = difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
        for line in diff:
            self.out(line.rstrip("\n"), min_verbosity=1)
