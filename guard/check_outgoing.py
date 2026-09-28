"""Find the owner's private words in what leaves the lab for the product.

Two modes, both over a git repository (``--repo``, the product checkout):

``--diff BASE..HEAD``
    The pre-pull-request check. Every commit reachable from HEAD and not from
    BASE is scanned on its own: the lines it adds, what a deletion creates
    (a backslash join or a word wrapped over the new line break, and nothing
    else next to it), the path names it adds, its commit message, and its
    author and committer lines (name and e-mail; not the timestamp or time
    zone, and no other header). A word added in one commit and removed in a
    later one is still found, because it still leaves in the pushed history.
    ``--branch NAME`` scans the branch name too. Tags, tag messages and git
    notes are not scanned. Every completed scan says how many commits it
    scanned.

    Refused with exit 2: staged, modified or untracked (non-ignored) files
    (they are in no range); a side of the range that starts with ``^`` or
    holds range syntax itself; a range given backwards (HEAD an ancestor of
    BASE); and, when the range is empty however it is spelled or HEAD is
    given as ``HEAD`` while detached, local branches holding commits that
    neither end of the range nor any remote-tracking ref contains.

``--tree``
    Scan every tracked file and every path name at HEAD. This measures how far
    the clean-up of the whole product still has to go. ``--count-only`` makes
    it informational: exit 0 whenever the scan ran.

The guard fails closed.

* Blobs are read with ``git cat-file`` and scanned as bytes; nothing is
  skipped because git calls it binary. Added lines are found by diffing blob
  against blob, where no ``.gitattributes`` rule applies. Replace objects are
  switched off, and a shallow or grafted repository is refused.
* A blob is *text* when the whole of it decodes, strictly, in a recognised
  encoding and holds none of U+0000-U+0008, U+000E-U+001A, U+001C-U+001F and
  U+007F (tab, line feed, vertical tab, form feed, carriage return and escape
  are allowed): UTF-8 (with or without
  a BOM), UTF-16 or UTF-32 with a BOM, UTF-32 without one, or UTF-16 without
  one whose NUL bytes all sit on one side of each code unit and make up at
  least 30% of it. There is no allowance for a few odd bytes.
* Any other blob is still searched (as UTF-8 with replacement, and, when it
  holds NUL bytes, as latin-1 with the NUL bytes removed) and is then listed
  as *not scanned as text*, which exits 2 unless its exact path is listed in
  ``binary-ok.txt``. Compressed or encoded content is never read through.
* Before matching, text is normalised: format characters (Unicode category
  Cf, such as soft hyphens, zero-width and direction marks), C1 controls
  U+0080-U+009F, U+2028, U+2029, variation selectors, tag characters, U+034F
  and U+180E are removed; Unicode NFKC is applied; every character of
  category Pd (dashes) and U+2212 (minus) becomes ``-``; a line ending in a
  backslash is joined with the next; and two neighbouring lines are also
  matched joined by one space, the lower one without its leading whitespace
  and comment markers (``#``, ``//``, ``*``, ``--``, ``>``, ``|``), keeping
  only matches that cross the join.

Output: one finding per line, ``path:line: pattern: matching text`` (followed
by ``(commit <id>)`` in ``--diff`` mode; a path name is line 0), the files not
scanned as text, then a summary counted per pattern and per top-level
directory. ``--quiet`` leaves out the finding lines and the list of files not
scanned as text (their count stays).

Exit codes: 0 clean, 1 findings, 2 usage, error, refused state or content not
scanned as text. An error never exits 0.

Standard library only.
"""

from __future__ import annotations

import argparse
import functools
import io
import os
import re
import subprocess
import sys
import threading
import unicodedata
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

HERE = Path(__file__).resolve().parent
DEFAULT_WORDS = HERE / "private-words.txt"
DEFAULT_ALLOWED = HERE / "allowed.txt"
DEFAULT_BINARY_OK = HERE / "binary-ok.txt"

TOP_LEVEL_FILES = "(top-level files)"
MESSAGE = "(commit message)"
IDENTITY = "(commit identity)"
BRANCH = "(branch name)"
PSEUDO_PATHS = {MESSAGE, IDENTITY, BRANCH}
GITLINK_MODE = "160000"

# Git with the outside influences on what it shows switched off: no user or
# system attributes file, no pager; textconv and external diff are refused on
# the diff command line itself.
GIT_BASE = [
    "git",
    "-c",
    "core.quotePath=false",
    "-c",
    "core.attributesFile=/dev/null",
    "--no-pager",
    "--no-replace-objects",
]
GIT_ENV = {**os.environ, "GIT_ATTR_NOSYSTEM": "1", "GIT_NO_REPLACE_OBJECTS": "1"}
GIT_ENV.pop("GIT_EXTERNAL_DIFF", None)

# A continuation line's leading whitespace and comment markers, removed before
# a line is joined to the one above it.
MARKERS = re.compile(r"^\s*(?:(?:#|//|\*|--|>|\|)\s*)*")
BREAKS = re.compile(r"\s*\n\s*(?:(?:#|//|\*|--|>|\|)\s*)*")
# Characters text does not hold: C0 controls other than tab, line feed,
# vertical tab, form feed, carriage return and escape; and DEL.
CONTROL = re.compile(r"[\x00-\x08\x0e-\x1a\x1c-\x1f\x7f]")
BOMS = [
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\xef\xbb\xbf", "utf-8"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]
# A pattern that refers to a group by number or name would change meaning
# inside the combined prefilter, where group numbers shift.
BACKREFERENCE = re.compile(r"(?<!\\)(?:\\\\)*\\(?:[1-9]|g<)|\(\?P=|\(\?\(")
HUNK = re.compile(rb"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)
INLINE_COMMENT = re.compile(r"\s+#.*$")


class GuardError(Exception):
    """Anything that makes a scan untrustworthy; always exit 2."""


@dataclass(frozen=True)
class Pattern:
    source: str
    regex: re.Pattern[str]


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    pattern: str
    text: str
    commit: str = ""

    def render(self) -> str:
        where = f"{self.path}:{self.line}: {self.pattern}: {self.text}"
        return f"{where}  (commit {self.commit})" if self.commit else where


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    not_scanned: dict[str, int] = field(default_factory=dict)  # path -> size
    commits: int | None = None  # scanned in --diff mode


# --- configuration files ------------------------------------------------------


def _read_config(path: Path) -> list[tuple[int, str]]:
    """(number, line) of a config file; a BOM, CRs and trailing space removed."""
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GuardError(f"cannot read {path}: {exc}") from exc
    text = text.removeprefix("﻿")
    return [
        (number, raw.rstrip("\r").rstrip())
        for number, raw in enumerate(text.split("\n"), start=1)
    ]


def load_patterns(path: Path) -> list[Pattern]:
    """One regular expression per line, matched case-insensitively.

    A line starting with `#` is a comment, and so is everything from a `#`
    that follows whitespace (`srv1  # host`); write `\\#` for a literal `#`.
    Leading and trailing whitespace is never part of a pattern.
    """
    patterns: list[Pattern] = []
    for number, raw in _read_config(path):
        line = INLINE_COMMENT.sub("", raw).strip()
        if not line or line.startswith("#"):
            continue
        if "\0" in line:
            raise GuardError(f"{path}:{number}: pattern holds a NUL byte")
        if unicodedata.normalize("NFKC", line) != line:
            raise GuardError(
                f"{path}:{number}: pattern {line!r} changes under NFKC; text is "
                "normalised before matching, so it could never match as written"
            )
        if BACKREFERENCE.search(line):
            raise GuardError(f"{path}:{number}: pattern {line!r} uses a backreference")
        try:
            regex = re.compile(line, re.IGNORECASE)
        except re.error as exc:
            raise GuardError(f"{path}:{number}: bad pattern {line!r}: {exc}") from exc
        if regex.groupindex:
            raise GuardError(f"{path}:{number}: pattern {line!r} names a group")
        if regex.search(""):
            raise GuardError(f"{path}:{number}: pattern {line!r} matches everything")
        patterns.append(Pattern(line, regex))
    if not patterns:
        raise GuardError(f"{path}: no patterns; an empty list would read as clean")
    return patterns


def load_allowed(path: Path) -> set[tuple[str, str]]:
    allowed: set[tuple[str, str]] = set()
    for number, raw in _read_config(path):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        file_path, sep, line_text = raw.partition(":")
        if not sep or not file_path:
            raise GuardError(f"{path}:{number}: expected 'path:exact line text'")
        if file_path in PSEUDO_PATHS:
            raise GuardError(f"{path}:{number}: {file_path} can never be allowed")
        allowed.add((file_path, line_text))
    return allowed


def load_exact_paths(path: Path) -> set[str]:
    """Exact paths, one per line; a glob character is refused."""
    paths = set()
    for number, raw in _read_config(path):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.search(r"[*?\[]", line):
            raise GuardError(f"{path}:{number}: {line!r}: exact paths only, no globs")
        paths.add(line)
    return paths


# --- matching -----------------------------------------------------------------


@functools.cache
def _normal_table() -> dict[int, str | None]:
    """Characters removed before matching, and dashes mapped to `-`.

    Removed: Unicode category Cf (format characters), C1 controls
    U+0080-U+009F, U+2028, U+2029, U+034F, U+180E, variation selectors and
    tag characters. Mapped to `-`: every character of category Pd, and U+2212.
    """
    table: dict[int, str | None] = {}
    for cp in range(sys.maxunicode + 1):
        category = unicodedata.category(chr(cp))
        if category == "Cf":
            table[cp] = None
        elif category == "Pd":
            table[cp] = "-"
    table[0x2212] = "-"
    removed = [
        *range(0x80, 0xA0),
        0x2028,
        0x2029,
        0x034F,
        0x180E,
        *range(0xFE00, 0xFE10),
        *range(0xE0000, 0xE0080),
        *range(0xE0100, 0xE01F0),
    ]
    for cp in removed:
        table[cp] = None
    return table


def normalise(text: str) -> str:
    if text.isascii():
        return text
    table = _normal_table()
    return unicodedata.normalize("NFKC", text.translate(table)).translate(table)


def logical_lines(lines: Sequence[str]) -> list[tuple[int, int]]:
    """(first, last) 0-based index of each line, joined over a trailing `\\`."""
    spans = []
    start = 0
    while start < len(lines):
        end = start
        while end + 1 < len(lines) and lines[end].rstrip("\r").endswith("\\"):
            end += 1
        spans.append((start, end))
        start = end + 1
    return spans


def _strict(blob: bytes, codec: str) -> str | None:
    """`blob` decoded, when all of it is text in `codec`; otherwise None."""
    try:
        text = blob.decode(codec)
    except UnicodeDecodeError:
        return None
    return None if CONTROL.search(text) else text


def recognise(blob: bytes) -> tuple[str, str] | None:
    """(codec, text) when the whole blob is text in a recognised encoding."""
    for bom, codec in BOMS:
        if blob.startswith(bom):
            text = _strict(blob[len(bom) :], codec)
            return (codec, text) if text is not None else None
    if b"\0" not in blob:
        text = _strict(blob, "utf-8")
        return ("utf-8", text) if text is not None else None
    candidates = []
    if len(blob) % 4 == 0:
        candidates += ["utf-32-le", "utf-32-be"]
    if len(blob) % 2 == 0:
        units = len(blob) // 2
        even, odd = blob[0::2].count(0), blob[1::2].count(0)
        if even == 0 and odd >= 0.3 * units:
            candidates.append("utf-16-le")
        if odd == 0 and even >= 0.3 * units:
            candidates.append("utf-16-be")
    for codec in candidates:
        text = _strict(blob, codec)
        if text is not None:
            return codec, text
    return None


def decodings(blob: bytes) -> tuple[list[str], bool, bool]:
    """(texts to search, is text, line numbers are git's).

    Git counts lines by the byte `\\n`; that holds for UTF-8 and not for
    UTF-16 or UTF-32.
    """
    found = recognise(blob)
    texts = [found[1]] if found is not None else []
    texts.append(blob.decode("utf-8", "replace"))
    if b"\0" in blob:
        texts.append(blob.replace(b"\0", b"").decode("latin-1"))
    aligned = found is not None and found[0] == "utf-8"
    return texts, found is not None, aligned


class Scanner:
    def __init__(
        self,
        patterns: Sequence[Pattern],
        allowed: set[tuple[str, str]],
        binary_ok: set[str],
    ) -> None:
        self.patterns = patterns
        self.allowed = allowed
        self.binary_ok = binary_ok
        # One pass to decide whether a text needs the per-pattern pass at all.
        # Backreferences and named groups are refused on load, so the shifted
        # group numbers in here cannot change what a pattern means.
        try:
            self.any = re.compile(
                "|".join(f"(?:{p.source})" for p in patterns), re.IGNORECASE
            )
        except re.error as exc:
            raise GuardError(f"the patterns do not combine: {exc}") from exc

    def _find(self, text: str) -> list[tuple[str, re.Match[str]]]:
        """(pattern, match) in `text`, which is already normalised."""
        if not self.any.search(text):
            return []
        return [(p.source, m) for p in self.patterns for m in p.regex.finditer(text)]

    def match(self, path: str, number: int, text: str, commit: str) -> list[Finding]:
        return [
            Finding(path, number, source, m.group(0), commit)
            for source, m in self._find(normalise(text))
        ]

    def path_name(self, path: str, commit: str = "") -> list[Finding]:
        return self.match(path, 0, path, commit)

    def _worth_scanning(self, text: str) -> bool:
        flat = normalise(text.replace("\\\r\n", "").replace("\\\n", ""))
        return bool(self.any.search(flat) or self.any.search(BREAKS.sub(" ", flat)))

    def lines(
        self,
        path: str,
        text: str,
        wanted: set[int] | None,
        commit: str = "",
        joins: frozenset[int] = frozenset(),
    ) -> list[Finding]:
        """Scan the lines numbered in `wanted` (1-based; None = every line).

        A line joined to its neighbours by trailing backslashes is one
        logical line, scanned whole and reported at its first line whenever
        any part of it is wanted. Two neighbouring logical lines are also
        matched joined by one space (the lower one without its leading
        whitespace and comment markers), keeping only matches that cross the
        join, when either is wanted: a word wrapped over a line break.

        `joins` holds the lines c whose neighbour c + 1 was brought next to
        them by a deletion. There only what crosses the new boundary is
        reported: a backslash join or a wrapped word the deletion created.
        """
        if wanted is None and not self._worth_scanning(text):
            return []
        raw = [line.rstrip("\r") for line in text.split("\n")]
        spans = logical_lines(raw)
        cache: dict[int, tuple[str, list[int]]] = {}

        def span_text(k: int) -> tuple[str, list[int]]:
            """Normalised text of span k, and the offsets of its inner joins."""
            if k not in cache:
                first, last = spans[k]
                pieces, offsets, size = [], [], 0
                for index in range(first, last + 1):
                    piece = raw[index][:-1] if index < last else raw[index]
                    piece = normalise(piece)
                    pieces.append(piece)
                    size += len(piece)
                    offsets.append(size)
                cache[k] = ("".join(pieces), offsets[:-1])
            return cache[k]

        def is_wanted(k: int) -> bool:
            first, last = spans[k]
            return wanted is None or any(
                n in wanted for n in range(first + 1, last + 2)
            )

        found: list[Finding] = []
        for k, (first, last) in enumerate(spans):
            if is_wanted(k):
                if first == last and (path, raw[first]) in self.allowed:
                    continue
                joined, _ = span_text(k)
                found.extend(
                    Finding(path, first + 1, source, m.group(0), commit)
                    for source, m in self._find(joined)
                )
                continue
            made = [c - (first + 1) for c in joins if first + 1 <= c <= last]
            if made:
                joined, offsets = span_text(k)
                cuts = [offsets[i] for i in made]
                found.extend(
                    Finding(path, first + 1, source, m.group(0), commit)
                    for source, m in self._find(joined)
                    if any(m.start() < cut < m.end() for cut in cuts)
                )
        for k in range(len(spans) - 1):
            if not (is_wanted(k) or is_wanted(k + 1) or spans[k][1] + 1 in joins):
                continue
            left = span_text(k)[0].rstrip()
            right = MARKERS.sub("", span_text(k + 1)[0])
            if not left or not right:
                continue
            cut = len(left)
            found.extend(
                Finding(path, spans[k][0] + 1, source, m.group(0), commit)
                for source, m in self._find(f"{left} {right}")
                if m.start() < cut and m.end() > cut + 1
            )
        return found

    def texts(
        self,
        path: str,
        texts: Sequence[str],
        wanted: set[int] | None,
        commit: str = "",
        joins: frozenset[int] = frozenset(),
    ) -> list[Finding]:
        """Scan several decodings of one content. The same occurrence found in
        two decodings is one finding; two occurrences on one line are two."""
        merged: Counter[Finding] = Counter()
        for text in texts:
            merged |= Counter(self.lines(path, text, wanted, commit, joins))
        return list(merged.elements())

    def blob(
        self,
        report: Report,
        path: str,
        blob: bytes,
        wanted: set[int] | None,
        commit: str = "",
        joins: frozenset[int] = frozenset(),
    ) -> None:
        """Scan a blob's content in every decoding."""
        texts, text_like, aligned = decodings(blob)
        if not text_like or not aligned:
            wanted, joins = None, frozenset()  # scan the whole blob
        report.findings.extend(self.texts(path, texts, wanted, commit, joins))
        if not text_like and path not in self.binary_ok:
            report.not_scanned[path] = len(blob)


# --- git ----------------------------------------------------------------------


def git(repo: Path, *args: str) -> bytes:
    command = [*GIT_BASE, "-C", str(repo), *args]
    try:
        done = subprocess.run(command, capture_output=True, check=False, env=GIT_ENV)
    except OSError as exc:
        raise GuardError(f"cannot run git: {exc}") from exc
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace").strip()
        raise GuardError(f"git {' '.join(args[:3])} failed: {detail}")
    return done.stdout


def git_yes(repo: Path, *args: str) -> bool:
    """True on exit 0, False on exit 1; anything else is an error."""
    command = [*GIT_BASE, "-C", str(repo), *args]
    try:
        done = subprocess.run(command, capture_output=True, check=False, env=GIT_ENV)
    except OSError as exc:
        raise GuardError(f"cannot run git: {exc}") from exc
    if done.returncode not in (0, 1):
        detail = done.stderr.decode("utf-8", "replace").strip()
        raise GuardError(f"git {' '.join(args[:3])} failed: {detail}")
    return done.returncode == 0


def check_repo(repo: Path) -> None:
    if not repo.is_dir():
        raise GuardError(f"{repo}: no such directory")
    inside = git(repo, "rev-parse", "--is-inside-work-tree").strip()
    if inside != b"true":
        raise GuardError(f"{repo}: not a git work tree")
    # Must be the top of its own work tree. An uninitialised submodule is an
    # empty directory inside the lab's work tree, and scanning the lab instead
    # of the product would report on the wrong repository.
    top = git(repo, "rev-parse", "--show-toplevel").decode().strip()
    if Path(top).resolve() != repo.resolve():
        raise GuardError(f"{repo}: not the top of a git work tree (that is {top})")
    # A shallow or grafted history hides commits and content from the scan.
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise GuardError(f"{repo} is a shallow clone; fetch its full history")
    grafts = git(repo, "rev-parse", "--git-path", "info/grafts").decode().strip()
    if (repo / grafts).exists() or Path(grafts).exists():
        raise GuardError(f"{repo} has a grafts file ({grafts}); remove it")


def check_clean(repo: Path) -> None:
    status = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = [e.decode("utf-8", "replace") for e in status.split(b"\0") if e]
    if entries:
        listing = "\n".join(f"  {e}" for e in entries)
        raise GuardError(
            f"{repo} has work that is not committed, so no range can contain it:\n"
            f"{listing}\ncommit or remove them, then run the guard again"
        )


def resolve(repo: Path, rev: str) -> str:
    """The commit `rev` names; a string git would read as an option is refused."""
    out = git(repo, "rev-parse", "--verify", "--end-of-options", f"{rev}^{{commit}}")
    return out.decode().strip()


def iter_blobs(repo: Path, shas: Sequence[str]) -> Iterator[tuple[str, bytes]]:
    """Stream (sha, content) for each sha, in order, from one git process."""
    if not shas:
        return
    command = [*GIT_BASE, "-C", str(repo), "cat-file", "--batch", "--buffer"]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=GIT_ENV,
    )
    assert process.stdin is not None and process.stdout is not None
    stdin, stdout = process.stdin, process.stdout

    # The ids are written from a second thread while this one reads: writing
    # them all first could fill stdout while git waits for a reader, and a
    # request-reply loop pays one pipe round trip per file.
    def feed() -> None:
        try:
            stdin.write(b"".join(sha.encode("ascii") + b"\n" for sha in shas))
        except BrokenPipeError:
            pass
        finally:
            stdin.close()

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    try:
        for sha in shas:
            header = stdout.readline().split()
            if len(header) != 3 or header[0].decode() != sha:
                raise GuardError(f"git cat-file: unexpected reply for {sha}: {header}")
            size = int(header[2])
            blob = stdout.read(size)
            if len(blob) != size or stdout.read(1) != b"\n":
                raise GuardError(f"git cat-file: short read for {sha}")
            yield sha, blob
    finally:
        stdout.close()
        writer.join()
        code = process.wait()
    if code != 0:
        raise GuardError(f"git cat-file exited {code}")


@dataclass(frozen=True)
class Wanted:
    sha: str
    lines: set[int] | None = None  # None: every line
    joins: frozenset[int] = frozenset()  # lines a deletion put next to c + 1


def scan_blobs(
    repo: Path,
    scanner: Scanner,
    report: Report,
    wanted: dict[str, Wanted],
    commit: str = "",
) -> None:
    """Scan each path's blob, reading each blob once."""
    by_sha: dict[str, list[str]] = {}
    for path, item in wanted.items():
        by_sha.setdefault(item.sha, []).append(path)
    for sha, blob in iter_blobs(repo, list(by_sha)):
        for path in by_sha[sha]:
            item = wanted[path]
            scanner.blob(report, path, blob, item.lines, commit, item.joins)


# --- tree mode ----------------------------------------------------------------


def selected(path: str, only: Sequence[str]) -> bool:
    """True when ``path`` falls under one of ``only`` (all paths if empty).

    An entry is a path prefix (``src`` covers ``src/...``); ``/`` stands for
    the files at the repository root.
    """
    if not only:
        return True
    for prefix in only:
        if prefix == "/":
            if "/" not in path:
                return True
        elif path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/"):
            return True
    return False


def scan_tree(
    repo: Path, scanner: Scanner, only: Sequence[str], report: Report
) -> None:
    listing = git(repo, "ls-tree", "-r", "-z", "--full-tree", "HEAD")
    wanted: dict[str, Wanted] = {}
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        meta, _, raw_path = entry.partition(b"\t")
        _mode, kind, sha = meta.decode().split()
        path = raw_path.decode("utf-8", "surrogateescape")
        if not selected(path, only):
            continue
        report.findings.extend(scanner.path_name(path))  # every entry, gitlinks too
        if kind == "blob":
            wanted[path] = Wanted(sha)
    scan_blobs(repo, scanner, report, wanted)


# --- diff mode ----------------------------------------------------------------


def parse_range(spec: str) -> tuple[str, str]:
    base, sep, head = spec.partition("...")
    if not sep:
        base, sep, head = spec.partition("..")
    if not sep or not base or not head:
        raise GuardError(f"--diff wants BASE..HEAD, got {spec!r}")
    for side in (base, head):
        if side.startswith("^") or any(t in side for t in ("..", "^!", "^@", "^-")):
            raise GuardError(f"--diff: {side!r} is not a single revision")
    return base, head


@dataclass(frozen=True)
class Change:
    status: str
    old_sha: str
    new_sha: str
    new_mode: str


def changes(repo: Path, parent: str, commit: str) -> dict[str, Change]:
    raw = git(
        repo,
        "diff-tree",
        "-r",
        "-z",
        "--no-renames",
        "--no-commit-id",
        "--raw",
        "--end-of-options",
        parent,
        commit,
    )
    parts = raw.split(b"\0")
    result: dict[str, Change] = {}
    index = 0
    while index + 1 < len(parts):
        meta = parts[index].decode()
        path = parts[index + 1].decode("utf-8", "surrogateescape")
        _old_mode, new_mode, old_sha, new_sha, status = meta.lstrip(":").split()
        result[path] = Change(status[:1], old_sha, new_sha, new_mode)
        index += 2
    return result


def added_lines(repo: Path, old_sha: str, new_sha: str) -> tuple[set[int], set[int]]:
    """(lines of blob `new_sha` not in `old_sha`, lines a deletion joined).

    The second set holds each line c after which lines were deleted, so that
    c and c + 1 are neighbours now. Diffed blob to blob: with no path, no
    attribute applies, and `--text --no-textconv --no-ext-diff` rule out the
    rest.
    """
    out = git(
        repo,
        "diff",
        "--text",
        "--no-textconv",
        "--no-ext-diff",
        "--no-color",
        "--unified=0",
        "--end-of-options",
        old_sha,
        new_sha,
    )
    added: set[int] = set()
    joins: set[int] = set()
    for match in HUNK.finditer(out):
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) is not None else 1
        if count == 0:
            joins.add(start)  # a pure deletion after line `start`
        else:
            added.update(range(start, start + count))
    return added, joins


def is_null(sha: str) -> bool:
    return set(sha) == {"0"}


def check_elsewhere(repo: Path, base: str, head: str, why: str) -> None:
    """Refuse when local branches hold work the range does not contain.

    Work is a commit on a local branch that is reachable from neither the
    base, the head, nor any remote-tracking ref (so not already pushed).
    """
    remotes = git(repo, "for-each-ref", "--format=%(objectname)", "refs/remotes/")
    exclude = [f"^{sha}" for sha in remotes.decode().split()]
    refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/")
    outside = []
    for ref in refs.decode("utf-8", "replace").split():
        count = git(
            repo,
            "rev-list",
            "--count",
            "--end-of-options",
            ref,
            f"^{base}",
            f"^{head}",
            *exclude,
        )
        if int(count) > 0:
            outside.append(f"{ref.removeprefix('refs/heads/')} ({int(count)} commits)")
    if outside:
        raise GuardError(
            f"{why}, while local branches hold commits outside the range: "
            f"{', '.join(outside)}. Check out the branch to send "
            "(git switch <branch>) and run the guard again, or pass its range"
        )


def commit_parts(raw: bytes) -> tuple[list[str], str, bytes]:
    """(parent ids, author and committer lines without timestamps, message)."""
    headers, _, message = raw.partition(b"\n\n")
    parents, identity = [], []
    for line in headers.split(b"\n"):
        if line.startswith(b"parent "):
            parents.append(line.split()[1].decode())
        elif line.startswith((b"author ", b"committer ")):
            identity.append(line[: line.rfind(b">") + 1])
    return parents, b"\n".join(identity).decode("utf-8", "replace"), message


def scan_diff(
    repo: Path,
    scanner: Scanner,
    spec: str,
    only: Sequence[str],
    branch: str | None,
    report: Report,
) -> None:
    check_clean(repo)
    base_rev, head_rev = parse_range(spec)
    base, head = resolve(repo, base_rev), resolve(repo, head_rev)
    if head != base and git_yes(repo, "merge-base", "--is-ancestor", head, base):
        raise GuardError(
            f"--diff {spec}: {head_rev} is behind {base_rev}; the range is backwards"
        )
    if head_rev in {"HEAD", "@"} and not git_yes(
        repo, "symbolic-ref", "--quiet", "HEAD"
    ):
        check_elsewhere(repo, base, head, f"HEAD is detached at {head[:7]}")
    if branch is not None:
        report.findings.extend(scanner.match(BRANCH, 0, branch, ""))
    commits = git(
        repo,
        "rev-list",
        "--reverse",
        "--topo-order",
        "--end-of-options",
        head,
        f"^{base}",
    ).split()
    if not commits:
        check_elsewhere(repo, base, head, f"--diff {spec} holds no commits")
    report.commits = len(commits)
    empty_tree = git(repo, "hash-object", "-t", "tree", "/dev/null").decode().strip()
    for raw_commit in commits:
        commit = raw_commit.decode()
        short = commit[:7]
        parents, identity, message = commit_parts(
            git(repo, "cat-file", "commit", commit)
        )
        report.findings.extend(scanner.lines(IDENTITY, identity, None, short))
        texts, is_text, _ = decodings(message)
        report.findings.extend(scanner.texts(MESSAGE, texts, None, short))
        if not is_text:
            report.not_scanned[f"{MESSAGE} {short}"] = len(message)
        scan_commit(repo, scanner, commit, short, parents or [empty_tree], only, report)


def scan_commit(
    repo: Path,
    scanner: Scanner,
    commit: str,
    short: str,
    parents: Sequence[str],
    only: Sequence[str],
    report: Report,
) -> None:
    """Scan what `commit` adds relative to every one of its parents.

    For a merge, a path counts only when it differs from every parent, and a
    line only when it is new relative to every parent.
    """
    per_parent = [changes(repo, parent, commit) for parent in parents]
    paths = set(per_parent[0]).intersection(*per_parent[1:])
    wanted: dict[str, Wanted] = {}
    for path in sorted(paths):
        if not selected(path, only):
            continue
        entries = [p[path] for p in per_parent]
        if all(e.status == "D" for e in entries):
            continue
        if all(e.status == "A" for e in entries):
            report.findings.extend(scanner.path_name(path, short))
        new = entries[0]
        if new.new_mode == GITLINK_MODE or is_null(new.new_sha):
            continue
        lines: set[int] | None = None
        joins: set[int] | None = None
        for entry in entries:
            if entry.status == "A" or is_null(entry.old_sha):
                continue  # everything is new relative to this parent
            added, joined = added_lines(repo, entry.old_sha, entry.new_sha)
            lines = added if lines is None else lines & added
            joins = joined if joins is None else joins & joined
        wanted[path] = Wanted(new.new_sha, lines, frozenset(joins or ()))
    scan_blobs(repo, scanner, report, wanted, short)


# --- output -------------------------------------------------------------------


def top_level(path: str) -> str:
    if path in PSEUDO_PATHS:
        return path
    head, sep, _ = path.partition("/")
    return head + "/" if sep else TOP_LEVEL_FILES


def summarise(report: Report, quiet: bool) -> list[str]:
    findings = report.findings
    lines = []
    if report.commits is not None:
        lines.append(f"commits scanned: {report.commits}")
    if report.not_scanned:
        lines.append(f"not scanned as text: {len(report.not_scanned)} files")
        if not quiet:
            for path, size in sorted(report.not_scanned.items()):
                lines.append(f"  {path} ({size} bytes)")
        lines.append(
            "  what to do: convert a text file to UTF-8 (without control "
            "characters); for a real binary, list its exact path in "
            "guard/binary-ok.txt"
        )
    files = {f.path for f in findings}
    lines.append(f"summary: {len(findings)} findings in {len(files)} files")
    if not findings:
        return lines
    lines.append("by pattern:")
    for name, count in Counter(f.pattern for f in findings).most_common():
        lines.append(f"  {count:7d}  {name}")
    lines.append("by top-level directory:")
    for name, count in Counter(top_level(f.path) for f in findings).most_common():
        lines.append(f"  {count:7d}  {name}")
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find the owner's private words in what leaves for the product."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--diff", metavar="BASE..HEAD", help="scan each commit of this range"
    )
    mode.add_argument(
        "--tree", action="store_true", help="scan every tracked file at HEAD"
    )
    parser.add_argument("--repo", default=".", help="git repository (default: .)")
    parser.add_argument("--branch", help="with --diff: also scan this branch name")
    parser.add_argument("--words", default=str(DEFAULT_WORDS), help="pattern file")
    parser.add_argument("--allowed", default=str(DEFAULT_ALLOWED), help="allow-list")
    parser.add_argument(
        "--binary-ok",
        default=str(DEFAULT_BINARY_OK),
        help="exact paths of binary files that may go out",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PREFIX",
        help="scan only paths under PREFIX (repeatable; '/' = top-level files)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="no finding lines, no file list"
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="with --tree: informational, exit 0 whenever the scan ran",
    )
    return parser


def _silence_stdout() -> None:
    """Send whatever is still buffered for stdout nowhere, so that the
    interpreter's own flush at exit cannot fail again and change the code."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except (OSError, ValueError):
        pass


def run(argv: Sequence[str] | None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors, 0 on --help
        return int(exc.code) if isinstance(exc.code, int) else EXIT_ERROR
    report = Report()
    try:
        if isinstance(sys.stdout, io.TextIOWrapper):
            # A path that is not UTF-8 is printed escaped, never a crash.
            sys.stdout.reconfigure(errors="backslashreplace")
        if args.branch is not None and not args.diff:
            raise GuardError("--branch goes with --diff")
        if args.count_only and not args.tree:
            raise GuardError("--count-only goes with --tree")
        scanner = Scanner(
            load_patterns(Path(args.words)),
            load_allowed(Path(args.allowed)),
            load_exact_paths(Path(args.binary_ok)),
        )
        repo = Path(args.repo)
        check_repo(repo)
        if args.tree:
            scan_tree(repo, scanner, args.only, report)
        else:
            scan_diff(repo, scanner, args.diff, args.only, args.branch, report)
        if not args.quiet:
            for finding in report.findings:
                print(finding.render())
        for line in summarise(report, args.quiet):
            print(line)
        sys.stdout.flush()
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except BaseException as exc:  # anything unforeseen must not read as clean
        _silence_stdout()
        if isinstance(exc, KeyboardInterrupt):
            print("error: interrupted", file=sys.stderr)
        else:
            print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if args.count_only:
        return EXIT_CLEAN
    if report.not_scanned:
        return EXIT_ERROR
    return EXIT_FINDINGS if report.findings else EXIT_CLEAN


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
