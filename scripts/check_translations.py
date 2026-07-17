#!/usr/bin/env python3
"""Fail when a catalog would put an untranslated string on a page.

Three ways that happens, all silent at runtime:

- an empty msgstr: gettext returns the msgid,
- a fuzzy entry: gettext ignores the translation and returns the msgid,
- a msgstr that still carries the [brackets]: the convention marks a string
  that never went through gettext, so brackets reaching a msgstr mean the
  translation was pasted, not written.

Run it from the repository root; it exits non-zero and names every offender.
"""

import re
import sys
from pathlib import Path

LITERAL = re.compile(r'^\s*"(.*)"\s*$')


def entries(path):
    """Yield every (line number, msgid, msgstr, fuzzy) of a .po file.

    Args:
        path: The .po file to read.

    Yields:
        Tuples of the msgid's line number, the joined msgid, the joined
        msgstr, and whether the entry is flagged fuzzy. The header entry
        (empty msgid) is skipped.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    index = 0
    fuzzy = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("#,") and "fuzzy" in line:
            fuzzy = True
            index += 1
            continue
        if not line.startswith("msgid "):
            index += 1
            continue

        lineno = index + 1
        msgid_parts = [LITERAL.match(line[len("msgid ") :]).group(1)]
        index += 1
        while index < len(lines) and LITERAL.match(lines[index]):
            msgid_parts.append(LITERAL.match(lines[index]).group(1))
            index += 1

        msgstr_parts = []
        if index < len(lines) and lines[index].startswith("msgstr "):
            msgstr_parts.append(LITERAL.match(lines[index][len("msgstr ") :]).group(1))
            index += 1
            while index < len(lines) and LITERAL.match(lines[index]):
                msgstr_parts.append(LITERAL.match(lines[index]).group(1))
                index += 1

        msgid = "".join(msgid_parts)
        if msgid:
            yield lineno, msgid, "".join(msgstr_parts), fuzzy
        fuzzy = False


def check(path):
    """Report every entry of a catalog that would render untranslated.

    Args:
        path: The .po file to check.

    Returns:
        A list of human-readable problems, empty when the catalog is clean.
    """
    problems = []
    for lineno, msgid, msgstr, fuzzy in entries(path):
        where = f"{path}:{lineno}"
        if fuzzy:
            problems.append(f"{where}: fuzzy, so gettext ignores it: {msgid!r}")
        elif not msgstr:
            problems.append(f"{where}: empty translation: {msgid!r}")
        elif "[" in msgstr or "]" in msgstr:
            problems.append(f"{where}: brackets left in translation: {msgstr!r}")
    return problems


catalogs = sorted(Path("locale").glob("*/LC_MESSAGES/*.po"))
if not catalogs:
    print("No catalog found under locale/", file=sys.stderr)
    raise SystemExit(1)

found = [problem for path in catalogs for problem in check(path)]
for problem in found:
    print(problem, file=sys.stderr)
print(f"{len(catalogs)} catalog(s) checked, {len(found)} problem(s)")
raise SystemExit(1 if found else 0)
