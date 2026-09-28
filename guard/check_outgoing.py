"""Find the owner's private words in what leaves the lab for the product.

Two modes, both over a git repository (``--repo``, the product checkout):

``--diff BASE..HEAD``
    The pre-pull-request check. Every commit reachable from HEAD and not from
    BASE is scanned on its own: the lines it adds, the path names it adds and
    its commit message (author and committer identity are not scanned). A
    word added in one commit and removed in a later one is still found,
    because it still leaves in the pushed history. ``--branch NAME`` scans the
    branch name too. The work tree must be clean: staged, modified or
    untracked (non-ignored) files are an error, because they are not in the
    range and would otherwise read as clean.

``--tree``
    Scan every tracked file and every path name at HEAD. This measures how far
    the clean-up of the whole product still has to go. ``--count-only`` makes
    it informational: exit 0 whenever the scan ran.

The guard fails closed. Nothing is skipped because git calls it binary, and
no ``.gitattributes`` rule on the outgoing branch can switch it off: blobs are
read with ``git cat-file`` and scanned as bytes, and added lines are found by
diffing blob against blob, where no attribute applies. Every blob is decoded
as UTF-8 (with replacement); UTF-16 content (a BOM, or the NUL pattern of
UTF-16) is decoded as UTF-16 as well, and other content with NUL bytes or
invalid UTF-8 as latin-1 as well. Content that is still not text is scanned
anyway and listed as *not scanned as text*, which exits 2 unless its path
matches a glob in ``binary-ok.txt``. Before matching, text is normalised with
Unicode NFKC, zero-width characters are removed, and a line ending in a
backslash is joined with the next.

Output: one finding per line, ``path:line: pattern: matching text`` (followed
by ``(commit <id>)`` in ``--diff`` mode; a path name is line 0), the files not
scanned as text, then a summary counted per pattern and per top-level
directory. ``--quiet`` leaves out the finding lines.

Exit codes: 0 clean, 1 findings, 2 usage, error or content not scanned as
text. An error never exits 0.

Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
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
BRANCH = "(branch name)"
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
]
GIT_ENV = {**os.environ, "GIT_ATTR_NOSYSTEM": "1"}
GIT_ENV.pop("GIT_EXTERNAL_DIFF", None)

ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))
# Characters a text file does not contain; used to tell text from binary.
NOT_TEXT = re.compile(r"[\x00-\x08\x0e-\x1a\x1c-\x1f\x7f�]")
C1_CONTROLS = re.compile(r"[\x80-\x9f]")
NOT_TEXT_LIMIT = 0.05
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
        try:
            regex = re.compile(line, re.IGNORECASE)
        except re.error as exc:
            raise GuardError(f"{path}:{number}: bad pattern {line!r}: {exc}") from exc
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
        allowed.add((file_path, line_text))
    return allowed


def load_globs(path: Path) -> list[str]:
    return [
        line.strip().lower()
        for _, line in _read_config(path)
        if line.strip() and not line.strip().startswith("#")
    ]


# --- matching -----------------------------------------------------------------


def normalise(text: str) -> str:
    if text.isascii():
        return text
    return unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH)


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


def utf16_codec(blob: bytes) -> str | None:
    if blob.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    sample = blob[:4096]
    half = len(sample) // 2
    if half < 2:
        return None
    even = sample[0::2].count(0) / half
    odd = sample[1::2].count(0) / half
    if odd >= 0.3 and even <= 0.05:
        return "utf-16-le"
    if even >= 0.3 and odd <= 0.05:
        return "utf-16-be"
    return None


def decodings(blob: bytes) -> tuple[list[str], bool, bool]:
    """(texts to scan, looks like text, line numbers are git's).

    Git counts lines by the byte `\\n`; that holds for UTF-8 and latin-1 and
    not for UTF-16.
    """
    codec = utf16_codec(blob)
    if codec is not None:
        wide = blob.decode(codec, "replace")
        return [wide, blob.decode("utf-8", "replace")], True, False
    if b"\0" not in blob:
        try:
            return [blob.decode("utf-8")], True, True
        except UnicodeDecodeError:
            pass
    utf8 = blob.decode("utf-8", "replace")
    latin = blob.decode("latin-1")
    return [utf8, latin], _text_like(utf8, latin), True


def _text_like(utf8: str, latin: str) -> bool:
    if not latin:
        return True
    as_utf8 = len(NOT_TEXT.findall(utf8)) / max(len(utf8), 1)
    as_latin = (len(NOT_TEXT.findall(latin)) + len(C1_CONTROLS.findall(latin))) / len(
        latin
    )
    return min(as_utf8, as_latin) <= NOT_TEXT_LIMIT


class Scanner:
    def __init__(
        self,
        patterns: Sequence[Pattern],
        allowed: set[tuple[str, str]],
        binary_ok: Sequence[str],
    ) -> None:
        self.patterns = patterns
        self.allowed = allowed
        self.binary_ok = binary_ok
        # One pass to decide whether a text needs the per-pattern pass at all.
        self.any = re.compile(
            "|".join(f"(?:{p.source})" for p in patterns), re.IGNORECASE
        )

    def match(self, path: str, number: int, text: str, commit: str) -> list[Finding]:
        text = normalise(text)
        if not self.any.search(text):
            return []
        return [
            Finding(path, number, pattern.source, m.group(0), commit)
            for pattern in self.patterns
            for m in pattern.regex.finditer(text)
        ]

    def path_name(self, path: str, commit: str = "") -> list[Finding]:
        return self.match(path, 0, path, commit)

    def lines(
        self, path: str, text: str, wanted: set[int] | None, commit: str = ""
    ) -> list[Finding]:
        """Scan the lines numbered in `wanted` (1-based; None = every line).

        A line joined to its neighbours by trailing backslashes is scanned as
        one, reported at its first line, whenever any part of it is wanted.
        """
        if wanted is None:
            joined = text.replace("\\\r\n", "").replace("\\\n", "")
            if not self.any.search(normalise(joined)):
                return []
        lines = text.split("\n")
        found: list[Finding] = []
        for first, last in logical_lines(lines):
            if wanted is not None and not any(
                n in wanted for n in range(first + 1, last + 2)
            ):
                continue
            if first == last and (path, lines[first].rstrip("\r")) in self.allowed:
                continue
            parts = [line.rstrip("\r") for line in lines[first : last + 1]]
            joined = "".join(p[:-1] for p in parts[:-1]) + parts[-1]
            found.extend(self.match(path, first + 1, joined, commit))
        return found

    def blob(
        self,
        report: Report,
        path: str,
        blob: bytes,
        wanted: set[int] | None,
        commit: str = "",
    ) -> None:
        """Scan a blob's content in every decoding; see below for duplicates."""
        texts, text_like, aligned = decodings(blob)
        if not text_like or not aligned:
            wanted = None  # line numbers do not apply; scan the whole blob
        # The same occurrence found in two decodings is one finding; two
        # occurrences on one line are two. Keep each finding's highest count.
        merged: Counter[Finding] = Counter()
        for text in texts:
            merged |= Counter(self.lines(path, text, wanted, commit))
        report.findings.extend(merged.elements())
        if not text_like and not self.is_binary_ok(path):
            report.not_scanned[path] = len(blob)

    def is_binary_ok(self, path: str) -> bool:
        lowered = path.lower()
        return any(fnmatch.fnmatchcase(lowered, glob) for glob in self.binary_ok)


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


def scan_blobs(
    repo: Path,
    scanner: Scanner,
    report: Report,
    wanted: dict[str, tuple[str, set[int] | None]],
    commit: str = "",
) -> None:
    """Scan path -> (blob sha, wanted lines), reading each blob once."""
    by_sha: dict[str, list[str]] = {}
    for path, (sha, _) in wanted.items():
        by_sha.setdefault(sha, []).append(path)
    for sha, blob in iter_blobs(repo, list(by_sha)):
        for path in by_sha[sha]:
            scanner.blob(report, path, blob, wanted[path][1], commit)


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
    wanted: dict[str, tuple[str, set[int] | None]] = {}
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
            wanted[path] = (sha, None)
    scan_blobs(repo, scanner, report, wanted)


# --- diff mode ----------------------------------------------------------------


def parse_range(spec: str) -> tuple[str, str]:
    base, sep, head = spec.partition("...")
    if not sep:
        base, sep, head = spec.partition("..")
    if not sep or not base or not head:
        raise GuardError(f"--diff wants BASE..HEAD, got {spec!r}")
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


def added_lines(repo: Path, old_sha: str, new_sha: str) -> set[int]:
    """Line numbers of blob `new_sha` that are not in blob `old_sha`.

    Diffed blob to blob: with no path, no attribute applies, and `--text
    --no-textconv --no-ext-diff` rule out the rest.
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
    lines: set[int] = set()
    for match in HUNK.finditer(out):
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) is not None else 1
        lines.update(range(start, start + count))
    return lines


def is_null(sha: str) -> bool:
    return set(sha) == {"0"}


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
    empty_tree = git(repo, "hash-object", "-t", "tree", "/dev/null").decode().strip()
    for raw_commit in commits:
        commit = raw_commit.decode()
        short = commit[:7]
        raw = git(repo, "cat-file", "commit", commit)
        headers, _, message_bytes = raw.partition(b"\n\n")
        for text in decodings(message_bytes)[0]:
            report.findings.extend(scanner.lines(MESSAGE, text, None, short))
        parents = [
            line.split()[1].decode()
            for line in headers.split(b"\n")
            if line.startswith(b"parent ")
        ] or [empty_tree]
        scan_commit(repo, scanner, commit, short, parents, only, report)


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
    wanted: dict[str, tuple[str, set[int] | None]] = {}
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
        for entry in entries:
            if entry.status == "A" or is_null(entry.old_sha):
                continue  # everything is new relative to this parent
            added = added_lines(repo, entry.old_sha, entry.new_sha)
            lines = added if lines is None else lines & added
        wanted[path] = (new.new_sha, lines)
    scan_blobs(repo, scanner, report, wanted, short)


# --- output -------------------------------------------------------------------


def top_level(path: str) -> str:
    if path in {MESSAGE, BRANCH}:
        return path
    head, sep, _ = path.partition("/")
    return head + "/" if sep else TOP_LEVEL_FILES


def summarise(report: Report) -> list[str]:
    findings = report.findings
    lines = []
    if report.not_scanned:
        lines.append(f"not scanned as text: {len(report.not_scanned)} files")
        for path, size in sorted(report.not_scanned.items()):
            lines.append(f"  {path} ({size} bytes)")
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
        "--binary-ok", default=str(DEFAULT_BINARY_OK), help="globs of binary files"
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PREFIX",
        help="scan only paths under PREFIX (repeatable; '/' = top-level files)",
    )
    parser.add_argument("--quiet", action="store_true", help="no finding lines")
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="with --tree: informational, exit 0 whenever the scan ran",
    )
    return parser


def run(argv: Sequence[str] | None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors, 0 on --help
        return int(exc.code) if isinstance(exc.code, int) else EXIT_ERROR
    report = Report()
    try:
        if args.branch is not None and not args.diff:
            raise GuardError("--branch goes with --diff")
        if args.count_only and not args.tree:
            raise GuardError("--count-only goes with --tree")
        scanner = Scanner(
            load_patterns(Path(args.words)),
            load_allowed(Path(args.allowed)),
            load_globs(Path(args.binary_ok)),
        )
        repo = Path(args.repo)
        check_repo(repo)
        if args.tree:
            scan_tree(repo, scanner, args.only, report)
        else:
            scan_diff(repo, scanner, args.diff, args.only, args.branch, report)
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # anything unforeseen must not read as clean
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not args.quiet:
        for finding in report.findings:
            print(finding.render())
    for line in summarise(report):
        print(line)
    if args.count_only:
        return EXIT_CLEAN
    if report.not_scanned:
        return EXIT_ERROR
    return EXIT_FINDINGS if report.findings else EXIT_CLEAN


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
