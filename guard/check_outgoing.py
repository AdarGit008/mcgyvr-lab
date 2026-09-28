"""Find the owner's private words in what leaves the lab for the product.

Two modes, both over a git repository (``--repo``, the product checkout):

``--diff BASE..HEAD``
    Scan only the lines ADDED by the commits in the range: the commits
    reachable from HEAD and not from BASE, diffed from their merge base. This
    is the check that runs before a pull request is opened: it fails on what
    the branch adds, not on what was already there.

``--tree``
    Scan every tracked text file at HEAD. This measures how far the clean-up
    of the whole product still has to go.

Both modes also check the names of the paths they scan (a directory named
after a host leaks as much as a line does); such a finding is reported on
line 0. Binary files are skipped (a NUL byte in the first 8000 bytes, the same
test git uses).

Output: one finding per line, ``path:line: pattern: matching text``, then a
summary counted per pattern and per top-level directory. ``--quiet`` prints
the summary only.

Exit codes: 0 clean, 1 findings, 2 usage or error. An error never exits 0.

Standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

HERE = Path(__file__).resolve().parent
DEFAULT_WORDS = HERE / "private-words.txt"
DEFAULT_ALLOWED = HERE / "allowed.txt"

BINARY_SNIFF = 8000
TOP_LEVEL_FILES = "(top-level files)"


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

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.pattern}: {self.text}"


def _content_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Yield (line number, stripped line) for non-blank, non-comment lines."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuardError(f"cannot read {path}: {exc}") from exc
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line and not line.startswith("#"):
            yield number, line


def load_patterns(path: Path) -> list[Pattern]:
    patterns: list[Pattern] = []
    for number, line in _content_lines(path):
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
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuardError(f"cannot read {path}: {exc}") from exc
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        file_path, sep, line_text = raw.partition(":")
        if not sep or not file_path:
            raise GuardError(f"{path}:{number}: expected 'path:exact line text'")
        allowed.add((file_path, line_text))
    return allowed


class Scanner:
    def __init__(
        self, patterns: Sequence[Pattern], allowed: set[tuple[str, str]]
    ) -> None:
        self.patterns = patterns
        self.allowed = allowed
        # One pass to decide whether a text needs the per-pattern pass at all.
        self.any = re.compile(
            "|".join(f"(?:{p.source})" for p in patterns), re.IGNORECASE
        )

    def line(self, path: str, number: int, text: str) -> Iterator[Finding]:
        if not self.any.search(text) or (path, text) in self.allowed:
            return
        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                yield Finding(path, number, pattern.source, match.group(0))

    def path_name(self, path: str) -> Iterator[Finding]:
        for pattern in self.patterns:
            for match in pattern.regex.finditer(path):
                yield Finding(path, 0, pattern.source, match.group(0))

    def text(self, path: str, content: str) -> Iterator[Finding]:
        if not self.any.search(content):
            return
        for number, line in enumerate(content.splitlines(), start=1):
            yield from self.line(path, number, line)


def git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    command = ["git", "-C", str(repo), "-c", "core.quotePath=false", *args]
    try:
        done = subprocess.run(command, input=stdin, capture_output=True, check=False)
    except OSError as exc:
        raise GuardError(f"cannot run git: {exc}") from exc
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace").strip()
        raise GuardError(f"git {' '.join(args[:2])} failed: {detail}")
    return done.stdout


def check_repo(repo: Path) -> None:
    if not repo.is_dir():
        raise GuardError(f"{repo}: no such directory")
    inside = git(repo, "rev-parse", "--is-inside-work-tree").strip()
    if inside != b"true":
        raise GuardError(f"{repo}: not a git work tree")


def is_binary(blob: bytes) -> bool:
    return b"\0" in blob[:BINARY_SNIFF]


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


def scan_tree(repo: Path, scanner: Scanner, only: Sequence[str]) -> Iterator[Finding]:
    listing = git(repo, "ls-tree", "-r", "-z", "--full-tree", "HEAD")
    blobs: list[tuple[str, str]] = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        meta, _, raw_path = entry.partition(b"\t")
        _mode, kind, sha = meta.split()
        path = raw_path.decode("utf-8", "surrogateescape")
        if kind != b"blob" or not selected(path, only):
            continue
        blobs.append((path, sha.decode("ascii")))
    for path, _sha in blobs:
        yield from scanner.path_name(path)
    yield from _scan_blobs(repo, scanner, blobs)


def _scan_blobs(
    repo: Path, scanner: Scanner, blobs: Sequence[tuple[str, str]]
) -> Iterator[Finding]:
    if not blobs:
        return
    command = ["git", "-C", str(repo), "cat-file", "--batch", "--buffer"]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdin is not None and process.stdout is not None
    stdin, stdout = process.stdin, process.stdout

    # The ids are written from a second thread while this one reads: writing
    # them all first could fill stdout while git waits for a reader, and a
    # request-reply loop pays one pipe round trip per file.
    def feed() -> None:
        try:
            stdin.write(b"".join(sha.encode("ascii") + b"\n" for _, sha in blobs))
        except BrokenPipeError:
            pass
        finally:
            stdin.close()

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    try:
        for path, sha in blobs:
            header = stdout.readline().split()
            if len(header) != 3 or header[0].decode() != sha or header[1] != b"blob":
                raise GuardError(f"git cat-file: unexpected reply for {path}: {header}")
            size = int(header[2])
            blob = stdout.read(size)
            if len(blob) != size or stdout.read(1) != b"\n":
                raise GuardError(f"git cat-file: short read for {path}")
            if is_binary(blob):
                continue
            yield from scanner.text(path, blob.decode("utf-8", "replace"))
    finally:
        stdout.close()
        writer.join()
        code = process.wait()
    if code != 0:
        raise GuardError(f"git cat-file exited {code}")


def _unquote(path: str) -> str:
    """Undo git's C-style quoting of an unusual path."""
    if not (path.startswith('"') and path.endswith('"')):
        return path
    body = path[1:-1].encode("latin-1", "backslashreplace")
    return body.decode("unicode_escape").encode("latin-1").decode("utf-8", "replace")


def parse_range(spec: str) -> tuple[str, str]:
    base, sep, head = spec.partition("...")
    if not sep:
        base, sep, head = spec.partition("..")
    if not sep or not base or not head:
        raise GuardError(f"--diff wants BASE..HEAD, got {spec!r}")
    return base, head


def scan_diff(
    repo: Path, scanner: Scanner, spec: str, only: Sequence[str]
) -> Iterator[Finding]:
    base, head = parse_range(spec)
    merge_base = git(repo, "merge-base", base, head).decode().strip()
    # Paths the range creates (added, copied, renamed-to): their names are new.
    status = git(
        repo, "diff", "--name-status", "-z", "--find-renames", merge_base, head
    ).split(b"\0")
    index = 0
    while index < len(status) - 1:
        code = status[index].decode()
        if code[:1] in {"R", "C"}:
            new = status[index + 2]
            index += 3
        else:
            new = status[index + 1]
            index += 2
        path = new.decode("utf-8", "surrogateescape")
        if code[:1] in {"A", "R", "C"} and selected(path, only):
            yield from scanner.path_name(path)
    # Lines the range adds. `--text` is not passed: binary files show as
    # "Binary files ... differ" and carry no `+` lines, so they are skipped.
    diff = git(
        repo,
        "diff",
        "--unified=0",
        "--no-color",
        "--no-ext-diff",
        "--find-renames",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        merge_base,
        head,
    )
    yield from parse_added(diff.decode("utf-8", "replace"), scanner, only)


HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_added(diff: str, scanner: Scanner, only: Sequence[str]) -> Iterator[Finding]:
    """Yield findings on the `+` lines of a `--unified=0` diff.

    Hunk bodies are consumed by the counts in their headers, so an added line
    that itself starts with `++ ` is never mistaken for a file header.
    """
    path: str | None = None
    number = 0
    old_left = new_left = 0
    for line in diff.split("\n"):
        if old_left or new_left:
            if line.startswith("+"):
                if path is not None:
                    yield from scanner.line(path, number, line[1:].rstrip("\r"))
                number += 1
                new_left -= 1
            elif line.startswith("-"):
                old_left -= 1
            elif not line.startswith("\\"):  # "\ No newline at end of file"
                raise GuardError(f"unexpected line inside a hunk: {line!r}")
        elif line.startswith("diff --git "):
            path = None
        elif line.startswith("+++ "):
            target = _unquote(line[4:].rstrip("\t"))
            path = target[2:] if target.startswith("b/") else None
            if path is not None and not selected(path, only):
                path = None
        elif line.startswith("@@"):
            match = HUNK.match(line)
            if match is None:
                raise GuardError(f"cannot parse hunk header: {line!r}")
            old_left = int(match.group(1) or "1")
            number = int(match.group(2))
            new_left = int(match.group(3) or "1")
    if old_left or new_left:
        raise GuardError("diff ended inside a hunk")


def top_level(path: str) -> str:
    head, sep, _ = path.partition("/")
    return head + "/" if sep else TOP_LEVEL_FILES


def summarise(findings: Sequence[Finding]) -> list[str]:
    files = {f.path for f in findings}
    lines = [f"summary: {len(findings)} findings in {len(files)} files"]
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
        "--diff", metavar="BASE..HEAD", help="scan lines added by this commit range"
    )
    mode.add_argument(
        "--tree", action="store_true", help="scan every tracked file at HEAD"
    )
    parser.add_argument("--repo", default=".", help="git repository (default: .)")
    parser.add_argument("--words", default=str(DEFAULT_WORDS), help="pattern file")
    parser.add_argument("--allowed", default=str(DEFAULT_ALLOWED), help="allow-list")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PREFIX",
        help="scan only paths under PREFIX (repeatable; '/' = top-level files)",
    )
    parser.add_argument("--quiet", action="store_true", help="print the summary only")
    return parser


def run(argv: Sequence[str] | None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors, 0 on --help
        return int(exc.code) if isinstance(exc.code, int) else EXIT_ERROR
    try:
        scanner = Scanner(
            load_patterns(Path(args.words)), load_allowed(Path(args.allowed))
        )
        repo = Path(args.repo)
        check_repo(repo)
        found: Iterable[Finding]
        if args.tree:
            found = scan_tree(repo, scanner, args.only)
        else:
            found = scan_diff(repo, scanner, args.diff, args.only)
        findings: list[Finding] = []
        for finding in found:
            findings.append(finding)
            if not args.quiet:
                print(finding.render())
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # anything unforeseen must not read as clean
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    for line in summarise(findings):
        print(line)
    return EXIT_FINDINGS if findings else EXIT_CLEAN


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
