"""Self-tests for guard/check_outgoing.py, run against invented repositories."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[2]
SCRIPT = LAB / "guard" / "check_outgoing.py"
REAL_WORDS = LAB / "guard" / "private-words.txt"
REAL_ALLOWED = LAB / "guard" / "allowed.txt"

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


@dataclass
class Result:
    code: int
    out: str
    err: str


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir()
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(self.root), *args],
            env=GIT_ENV,
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout.strip()

    def write(self, path: str, content: str | bytes) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def words(tmp_path: Path) -> Path:
    path = tmp_path / "words.txt"
    path.write_text("# test words\n\\bsrv1\\b\nsecrethost\n", encoding="utf-8")
    return path


@pytest.fixture
def allowed(tmp_path: Path) -> Path:
    path = tmp_path / "allowed.txt"
    path.write_text("# none\n", encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    repo = Repo(tmp_path / "repo")
    repo.write("README.md", "# A product\n\nNothing private here.\n")
    repo.commit("base")
    return repo


def guard(repo: Path, words: Path, allowed: Path, *args: str) -> Result:
    done = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--words",
            str(words),
            "--allowed",
            str(allowed),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return Result(done.returncode, done.stdout, done.stderr)


def test_clean_diff_passes(repo: Repo, words: Path, allowed: Path) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "print('hello')\n")
    repo.commit("clean change")
    result = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert result.code == 0, result
    assert "summary: 0 findings" in result.out


def test_added_private_word_fails_and_names_path_line_pattern(
    repo: Repo, words: Path, allowed: Path
) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "a = 1\nHOST = 'SRV1'\n")
    repo.commit("leak")
    result = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert result.code == 1, result
    assert "src/app.py:2: \\bsrv1\\b: SRV1" in result.out.splitlines()
    assert "src/" in result.out


def test_untouched_old_word_passes_diff_but_fails_tree(
    repo: Repo, words: Path, allowed: Path
) -> None:
    repo.write("notes.txt", "runs on srv1\n")
    base = repo.commit("old leak")
    repo.write("notes.txt", "runs on srv1\nand is fine\n")
    repo.write("other.txt", "unrelated\n")
    repo.commit("touch nearby")
    diff = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert diff.code == 0, diff
    tree = guard(repo.root, words, allowed, "--tree")
    assert tree.code == 1, tree
    assert "notes.txt:1: \\bsrv1\\b: srv1" in tree.out


def test_diff_ignores_what_the_base_branch_added(
    repo: Repo, words: Path, allowed: Path
) -> None:
    repo.git("switch", "-q", "-c", "feature")
    repo.write("feature.txt", "clean\n")
    repo.commit("feature")
    repo.git("switch", "-q", "main")
    repo.write("main.txt", "secrethost\n")
    repo.commit("main moves on")
    result = guard(repo.root, words, allowed, "--diff", "main..feature")
    assert result.code == 0, result


def test_allow_listed_line_passes(repo: Repo, words: Path, tmp_path: Path) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("README.md", "# A product\n\nDeveloped on srv1.\n")
    repo.commit("the one allowed line")
    allow = tmp_path / "allow.txt"
    allow.write_text("# ok\nREADME.md:Developed on srv1.\n", encoding="utf-8")
    assert guard(repo.root, words, allow, "--diff", f"{base}..HEAD").code == 0
    assert guard(repo.root, words, allow, "--tree").code == 0
    # The same text anywhere else is still a finding.
    repo.write("docs/x.md", "Developed on srv1.\n")
    repo.commit("copy")
    assert guard(repo.root, words, allow, "--tree").code == 1


def test_broken_pattern_file_exits_2(repo: Repo, tmp_path: Path, allowed: Path) -> None:
    bad = tmp_path / "bad.txt"
    bad.write_text("srv1\n(unclosed\n", encoding="utf-8")
    result = guard(repo.root, bad, allowed, "--tree")
    assert result.code == 2, result
    assert "bad pattern" in result.err


def test_empty_pattern_file_exits_2(repo: Repo, tmp_path: Path, allowed: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("# only comments\n\n", encoding="utf-8")
    assert guard(repo.root, empty, allowed, "--tree").code == 2


def test_missing_repo_exits_2(tmp_path: Path, words: Path, allowed: Path) -> None:
    assert guard(tmp_path / "nowhere", words, allowed, "--tree").code == 2
    plain = tmp_path / "plain"
    plain.mkdir()
    assert guard(plain, words, allowed, "--tree").code == 2


def test_bad_range_and_bad_allow_list_exit_2(
    repo: Repo, words: Path, tmp_path: Path, allowed: Path
) -> None:
    assert guard(repo.root, words, allowed, "--diff", "nosuch..HEAD").code == 2
    assert guard(repo.root, words, allowed, "--diff", "HEAD").code == 2
    broken = tmp_path / "broken-allow.txt"
    broken.write_text("no separator here\n", encoding="utf-8")
    assert guard(repo.root, words, broken, "--tree").code == 2
    assert guard(repo.root, words, allowed).code == 2  # no mode given


def test_binary_files_are_skipped(repo: Repo, words: Path, allowed: Path) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("blob.bin", b"\x00\x01srv1 secrethost\x00")
    repo.commit("binary")
    assert guard(repo.root, words, allowed, "--diff", f"{base}..HEAD").code == 0
    assert guard(repo.root, words, allowed, "--tree").code == 0


def test_private_path_name_is_a_finding(repo: Repo, words: Path, allowed: Path) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("tools/srv1/run.sh", "echo hi\n")
    repo.commit("private directory name")
    diff = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert diff.code == 1
    assert "tools/srv1/run.sh:0: \\bsrv1\\b: srv1" in diff.out
    assert guard(repo.root, words, allowed, "--tree").code == 1


def test_added_line_that_looks_like_a_header_is_still_scanned(
    repo: Repo, words: Path, allowed: Path
) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("x.txt", "++ secrethost\n-- fine\n")
    repo.commit("tricky lines")
    result = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert result.code == 1, result
    assert "x.txt:1: secrethost: secrethost" in result.out


def test_quiet_prints_summary_only(repo: Repo, words: Path, allowed: Path) -> None:
    repo.write("a/one.txt", "srv1\nsecrethost\n")
    repo.commit("two")
    result = guard(repo.root, words, allowed, "--tree", "--quiet")
    assert result.code == 1
    assert not re.search(r"^\S+:\d+: ", result.out, re.MULTILINE)
    assert "summary: 2 findings in 1 files" in result.out
    assert "a/" in result.out


def test_only_restricts_the_tree(repo: Repo, words: Path, allowed: Path) -> None:
    repo.write("records/r.txt", "srv1\n")
    repo.write("src/s.txt", "clean\n")
    repo.commit("records")
    assert guard(repo.root, words, allowed, "--tree", "--only", "src").code == 0
    assert guard(repo.root, words, allowed, "--tree", "--only", "/").code == 0
    assert guard(repo.root, words, allowed, "--tree", "--only", "records").code == 1


def test_real_word_list_compiles_and_catches_the_seeds(
    repo: Repo, tmp_path: Path
) -> None:
    lines = [
        "srv1 and srv2",
        "the b-small box",
        "/home/adaramir/x",
        "tailbaf744.ts.net",
        "100.69.72.51",
        "RTX 3060 / GTX1660 / 1660 SUPER / GTX 1080 / 1080Ti",
        "a Z490 board",
        "unit srv2_35b_32k and d-srv1-dense",
        "see mcgyvr-lab",
    ]
    ordinary = ["timing out", "b-smaller", "Z4900", "1100.69.72.512", "srv10"]
    base = repo.git("rev-parse", "HEAD")
    repo.write("leak.txt", "\n".join(lines) + "\n")
    repo.write("fine.txt", "\n".join(ordinary) + "\n")
    repo.commit("seeds")
    result = guard(repo.root, REAL_WORDS, REAL_ALLOWED, "--diff", f"{base}..HEAD")
    assert result.code == 1, result
    hit_lines = {int(m) for m in re.findall(r"^leak\.txt:(\d+):", result.out, re.M)}
    assert hit_lines == set(range(1, len(lines) + 1))
    assert "fine.txt" not in result.out
    seeds = {
        line.strip()
        for line in REAL_WORDS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    hit_patterns = set(re.findall(r"^leak\.txt:\d+: (.+?): ", result.out, re.M))
    assert hit_patterns == seeds
