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

MAKE = ["make", "-f", str(LAB / "Makefile")]

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    # Submodules and clones of the invented repositories use file:// URLs.
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "protocol.file.allow",
    "GIT_CONFIG_VALUE_0": "always",
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
        self.git("add", "-A", ".")
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
    assert "src/app.py:2: \\bsrv1\\b: SRV1" in result.out
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


def test_directory_inside_another_repo_exits_2(
    repo: Repo, words: Path, allowed: Path
) -> None:
    # An uninitialised submodule: an empty directory in the outer work tree.
    (repo.root / "product").mkdir()
    assert guard(repo.root / "product", words, allowed, "--tree").code == 2


def test_bad_range_and_bad_allow_list_exit_2(
    repo: Repo, words: Path, tmp_path: Path, allowed: Path
) -> None:
    assert guard(repo.root, words, allowed, "--diff", "nosuch..HEAD").code == 2
    assert guard(repo.root, words, allowed, "--diff", "HEAD").code == 2
    broken = tmp_path / "broken-allow.txt"
    broken.write_text("no separator here\n", encoding="utf-8")
    assert guard(repo.root, words, broken, "--tree").code == 2
    assert guard(repo.root, words, allowed).code == 2  # no mode given


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


def findings(out: str) -> list[tuple[str, int, str]]:
    """(path, line, pattern) of every finding line in the output."""
    return [
        (m.group(1), int(m.group(2)), m.group(3))
        for m in re.finditer(r"^(.+?):(\d+): (.+?): ", out, re.MULTILINE)
    ]


# Every pattern of the REAL word list, with the text it exists to catch. The
# test below fails when a pattern is added without a sample, or when a
# sample stops being caught by its own pattern.
SAMPLES: dict[str, list[str]] = {
    "srv1(?![0-9])": ["srv1", "my_srv1_thing", "camelSrv1Host", "LIVE_SRV1"],
    "srv2(?![0-9])": ["read_srv2", "SRV2", "local_srv2"],
    "(?<![a-z0-9])b-small(?![a-z0-9])": ["b-small", "the_b-small box"],
    "adaramir": ["adaramir"],
    "/home/adaramir": ["/home/adaramir/x"],
    "tailbaf744": ["tailbaf744.ts.net"],
    r"(?<![0-9])100\.69\.72\.51(?![0-9])": ["100.69.72.51"],
    "RTX ?3060(?![0-9])": ["RTX 3060", "RTX3060", "rtx3060ti"],
    "GTX ?1660(?![0-9])": ["GTX1660", "GTX 1660"],
    "(?<![0-9])1660 ?SUPER": ["1660 SUPER", "1660SUPER"],
    "GTX ?1080(?![0-9])": ["GTX 1080", "gtx1080"],
    "(?<![0-9])1080 ?Ti(?![a-z])": ["1080Ti", "1080 Ti"],
    "(?<![0-9])Z490(?![0-9])": ["Z490", "boardZ490"],
    "srv[12]_[a-z0-9_]+": ["srv2_35b_32k", "my_srv1_x"],
    "d-srv[12]-[a-z0-9-]+": ["d-srv1-dense"],
    "mcgyvr-lab": ["mcgyvr-lab"],
}

ORDINARY = [
    "srv10",
    "srv12",
    "conserv1ng",
    "Z4900",
    "31660",
    "b-smaller",
    "RTX30600",
    "GTX10800",
    "GTX16600",
    "timing out",
    "1100.69.72.512",
    "1080 times",
]


def real_patterns() -> set[str]:
    patterns = set()
    for raw in REAL_WORDS.read_text(encoding="utf-8").splitlines():
        line = re.sub(r"\s+#.*$", "", raw).strip()
        if line and not line.startswith("#"):
            patterns.add(line)
    return patterns


def test_every_real_pattern_catches_its_samples(repo: Repo) -> None:
    assert real_patterns() == set(SAMPLES)
    lines = [(p, s) for p, samples in SAMPLES.items() for s in samples]
    repo.write("leak.txt", "\n".join(s for _, s in lines) + "\n")
    repo.commit("samples")
    result = guard(repo.root, REAL_WORDS, REAL_ALLOWED, "--tree")
    assert result.code == 1, result
    hits = {(n, p) for path, n, p in findings(result.out) if path == "leak.txt"}
    missed = [
        (pattern, sample)
        for number, (pattern, sample) in enumerate(lines, start=1)
        if (number, pattern) not in hits
    ]
    assert missed == []


def test_ordinary_words_pass_the_real_list(repo: Repo) -> None:
    repo.write("fine.txt", "\n".join(ORDINARY) + "\n")
    repo.commit("ordinary")
    result = guard(repo.root, REAL_WORDS, REAL_ALLOWED, "--tree")
    assert result.code == 0, result.out


def test_underscore_and_camel_case_do_not_hide_a_host(repo: Repo) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("run_srv1.txt", "x = LIVE_SRV1\ny = camelSrv1Host\n")
    repo.commit("hidden hosts")
    result = guard(repo.root, REAL_WORDS, REAL_ALLOWED, "--diff", f"{base}..HEAD")
    assert result.code == 1, result
    got = {(path, n) for path, n, _ in findings(result.out)}
    assert {("run_srv1.txt", 0), ("run_srv1.txt", 1), ("run_srv1.txt", 2)} <= got


# --- item 2: nothing is skipped because git calls it binary -----------------


def test_text_with_one_nul_byte_is_scanned(
    repo: Repo, words: Path, allowed: Path
) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("notes.txt", b"a normal text file that runs on srv1\n\x00\nend\n")
    repo.commit("nul")
    diff = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert diff.code == 1, diff
    assert "notes.txt:1: " in diff.out
    assert guard(repo.root, words, allowed, "--tree").code == 1


def test_utf16_text_is_scanned(repo: Repo, words: Path, allowed: Path) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("wide.txt", "hello\nruns on srv1\n".encode("utf-16"))
    repo.write("wide-nobom.txt", "runs on secrethost\n".encode("utf-16-le"))
    repo.commit("utf-16")
    diff = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert diff.code == 1, diff
    assert "wide.txt:" in diff.out and "wide-nobom.txt:" in diff.out
    tree = guard(repo.root, words, allowed, "--tree")
    assert "wide.txt:" in tree.out and "wide-nobom.txt:" in tree.out


def test_gitattributes_on_the_branch_cannot_switch_the_guard_off(
    repo: Repo, words: Path, allowed: Path
) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write(".gitattributes", "*.md -diff\n* binary\n")
    repo.write("doc.md", "deployed on srv1\n")
    repo.commit("hide it")
    diff = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert diff.code == 1, diff
    assert "doc.md:1: " in diff.out


def test_real_binary_is_listed_not_scanned_and_exits_2(
    repo: Repo, words: Path, allowed: Path
) -> None:
    base = repo.git("rev-parse", "HEAD")
    noise = bytes(range(256)) * 8
    repo.write("blob.bin", noise)
    repo.commit("binary")
    diff = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert diff.code == 2, diff
    assert "not scanned" in diff.out and "blob.bin" in diff.out
    assert "2048" in diff.out
    assert guard(repo.root, words, allowed, "--tree").code == 2


def test_binary_ok_globs_pass_but_their_names_are_scanned(
    repo: Repo, words: Path, allowed: Path
) -> None:
    base = repo.git("rev-parse", "HEAD")
    noise = bytes(range(256)) * 8
    repo.write("img/logo.png", noise)
    repo.commit("image")
    assert guard(repo.root, words, allowed, "--diff", f"{base}..HEAD").code == 0
    repo.write("img/srv1-rack.png", noise)
    repo.commit("image with a private name")
    diff = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert diff.code == 1, diff
    assert "img/srv1-rack.png:0: " in diff.out


# --- item 3: every commit of the range, its message, and the branch name ----


def test_a_word_added_then_removed_is_still_found(
    repo: Repo, words: Path, allowed: Path
) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("a.txt", "host srv1\n")
    leak = repo.commit("add")
    repo.write("a.txt", "host\n")
    repo.commit("remove")
    result = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert result.code == 1, result
    assert "a.txt:1: " in result.out
    assert leak[:7] in result.out


def test_a_commit_message_is_scanned(repo: Repo, words: Path, allowed: Path) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("a.txt", "fine\n")
    repo.commit("tune things\n\nmeasured on srv1 last night")
    result = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert result.code == 1, result
    assert "srv1" in result.out


def test_the_branch_name_is_scanned(repo: Repo, words: Path, allowed: Path) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("a.txt", "fine\n")
    repo.commit("fine")
    args = ("--diff", f"{base}..HEAD", "--branch")
    assert guard(repo.root, words, allowed, *args, "fix-srv1-wake").code == 1
    assert guard(repo.root, words, allowed, *args, "fix-wake").code == 0


def test_author_identity_is_not_scanned(repo: Repo, words: Path, allowed: Path) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("a.txt", "fine\n")
    repo.git("add", "a.txt")
    repo.git("commit", "-q", "-m", "fine", "--author", "secrethost <x@srv1.invalid>")
    assert guard(repo.root, words, allowed, "--diff", f"{base}..HEAD").code == 0


# --- item 4: uncommitted work is not clean ----------------------------------


@pytest.mark.parametrize("state", ["untracked", "staged", "modified"])
def test_uncommitted_work_exits_2(
    repo: Repo, words: Path, allowed: Path, state: str
) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("a.txt", "fine\n")
    repo.commit("fine")
    if state == "untracked":
        repo.write("new.txt", "srv1\n")
    elif state == "staged":
        repo.write("new.txt", "srv1\n")
        repo.git("add", "new.txt")
    else:
        repo.write("a.txt", "srv1\n")
    result = guard(repo.root, words, allowed, "--diff", f"{base}..HEAD")
    assert result.code == 2, result
    assert "commit or remove them" in result.err
    assert ("new.txt" if state != "modified" else "a.txt") in result.err


def test_ignored_files_are_not_uncommitted_work(
    repo: Repo, words: Path, allowed: Path
) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write(".gitignore", ".venv/\n")
    repo.commit("ignore")
    repo.write(".venv/x.txt", "srv1\n")
    assert guard(repo.root, words, allowed, "--diff", f"{base}..HEAD").code == 0


# --- item 6: a range end is a revision, never an option ---------------------


@pytest.mark.parametrize("spec", ["--independent..HEAD", "--octopus..HEAD"])
def test_option_like_range_ends_exit_2(
    repo: Repo, words: Path, allowed: Path, spec: str
) -> None:
    assert guard(repo.root, words, allowed, f"--diff={spec}").code == 2
    assert guard(repo.root, words, allowed, f"--diff=HEAD..{spec[:-6]}").code == 2


# --- item 7: pattern file syntax cannot disarm a pattern --------------------


@pytest.mark.parametrize(
    "content",
    [
        "\\bsrv9\\b  # a host\n",
        "\ufeff\\bsrv9\\b\n",
        "# comment\r\n\\bsrv9\\b   \r\n",
        "\\bsrv9\\b\t# tab comment\n",
    ],
)
def test_pattern_file_syntax_keeps_the_pattern_armed(
    repo: Repo, tmp_path: Path, allowed: Path, content: str
) -> None:
    words = tmp_path / "w.txt"
    words.write_bytes(content.encode("utf-8"))
    repo.write("a.txt", "on srv9 today\n")
    repo.commit("srv9")
    result = guard(repo.root, words, allowed, "--tree")
    assert result.code == 1, result
    assert "a.txt:1: \\bsrv9\\b: srv9" in result.out


def test_escaped_hash_is_part_of_the_pattern(
    repo: Repo, tmp_path: Path, allowed: Path
) -> None:
    words = tmp_path / "w.txt"
    words.write_text("issue \\#9\n", encoding="utf-8")
    repo.write("a.txt", "see issue #9\n")
    repo.commit("hash")
    assert guard(repo.root, words, allowed, "--tree").code == 1


# --- item 8: look-alikes ------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "runs on \uff53\uff52\uff56\uff11\n",  # fullwidth
        "runs on sr\u200bv1\n",
        "runs on s\u2060rv\ufeff1\n",
        "HOST=sr\\\nv1\n",
    ],
)
def test_look_alikes_are_caught(
    repo: Repo, words: Path, allowed: Path, text: str
) -> None:
    base = repo.git("rev-parse", "HEAD")
    repo.write("a.txt", text)
    repo.commit("look-alike")
    assert guard(repo.root, words, allowed, "--diff", f"{base}..HEAD").code == 1
    assert guard(repo.root, words, allowed, "--tree").code == 1


# --- item 9: gitlink path names ---------------------------------------------


def test_a_gitlink_path_name_is_scanned(repo: Repo, words: Path, allowed: Path) -> None:
    head = repo.git("rev-parse", "HEAD")
    repo.git("update-index", "--add", "--cacheinfo", f"160000,{head},vendor/srv1")
    repo.git("commit", "-q", "-m", "gitlink")
    (repo.root / "vendor" / "srv1").mkdir(parents=True)  # as git leaves one
    tree = guard(repo.root, words, allowed, "--tree")
    assert tree.code == 1, tree
    assert "vendor/srv1:0: " in tree.out
    diff = guard(repo.root, words, allowed, "--diff", f"{head}..HEAD")
    assert diff.code == 1, diff


# --- items 5 and 10: the make targets, run against an invented product -----


@dataclass
class Lab:
    root: Path
    origin: Repo
    product: Repo


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    origin = Repo(tmp_path / "origin")
    origin.write("README.md", "product\n")
    origin.commit("start")
    root = tmp_path / "lab"
    root.mkdir()
    subprocess.run(
        ["git", "clone", "-q", str(origin.root), str(root / "product")],
        env=GIT_ENV,
        check=True,
    )
    product = Repo.__new__(Repo)
    product.root = root / "product"
    return Lab(root, origin, product)


def make(lab: Lab, target: str) -> Result:
    done = subprocess.run(
        [*MAKE, "-C", str(lab.root), "--no-print-directory", target],
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    return Result(done.returncode, done.stdout, done.stderr)


def test_make_guard_is_the_gate(lab: Lab) -> None:
    lab.product.git("switch", "-q", "-c", "work")
    assert make(lab, "guard").code == 0
    lab.product.write("a.txt", "fine\n")
    lab.product.commit("fine")
    assert make(lab, "guard").code == 0
    lab.product.write("b.txt", "adaramir\n")
    lab.product.commit("leak")
    assert make(lab, "guard").code != 0


def test_make_guard_baseline_is_informational(lab: Lab) -> None:
    lab.product.write("b.txt", "adaramir\n")
    lab.product.commit("old leak")
    result = make(lab, "guard-baseline")
    assert result.code == 0, result
    assert "summary: 1 findings" in result.out


def test_product_sync_refuses_a_commit_on_no_branch(lab: Lab) -> None:
    lab.product.git("switch", "-q", "--detach")
    lab.product.write("a.txt", "work\n")
    orphan = lab.product.commit("work on no branch")
    result = make(lab, "product-sync")
    assert result.code != 0, result
    assert orphan[:7] in result.err
    assert lab.product.git("rev-parse", "HEAD") == orphan


def test_product_sync_moves_a_clean_checkout(lab: Lab) -> None:
    lab.origin.write("c.txt", "new\n")
    new = lab.origin.commit("upstream moves")
    result = make(lab, "product-sync")
    assert result.code == 0, result
    assert lab.product.git("rev-parse", "HEAD") == new


# --- item 5: the CI job's outgoing scan -------------------------------------

CI_SCRIPT = LAB / "guard" / "outgoing-ci.sh"


@dataclass
class CiLab:
    origin: Repo
    lab: Repo


@pytest.fixture
def ci_lab(tmp_path: Path) -> CiLab:
    origin = Repo(tmp_path / "origin")
    origin.write("README.md", "product\n")
    origin.commit("start")
    lab = Repo(tmp_path / "lab")
    lab.git("submodule", "add", "-q", "-b", "main", str(origin.root), "product")
    lab.commit("link the product")
    return CiLab(origin, lab)


def ci(lab: Repo, base: str) -> Result:
    done = subprocess.run(
        ["bash", str(CI_SCRIPT), base],
        cwd=lab.root,
        env={**GIT_ENV, "PYTHON": sys.executable},
        capture_output=True,
        text=True,
        check=False,
    )
    return Result(done.returncode, done.stdout, done.stderr)


def move_pointer(ci_lab: CiLab, content: str) -> None:
    product = ci_lab.lab.root / "product"
    subprocess.run(
        ["git", "-C", str(product), "switch", "-q", "-c", "work"],
        env=GIT_ENV,
        check=True,
    )
    (product / "change.txt").write_text(content, encoding="utf-8")
    for args in (["add", "change.txt"], ["commit", "-q", "-m", "change"]):
        subprocess.run(["git", "-C", str(product), *args], env=GIT_ENV, check=True)
    ci_lab.lab.git("add", "product")
    ci_lab.lab.git("commit", "-q", "-m", "move the pointer")


def test_ci_passes_when_the_pointer_did_not_move(ci_lab: CiLab) -> None:
    base = ci_lab.lab.git("rev-parse", "HEAD")
    ci_lab.lab.write("notes.txt", "lab work mentions adaramir freely\n")
    ci_lab.lab.commit("lab only")
    result = ci(ci_lab.lab, base)
    assert result.code == 0, result
    assert "did not move" in result.out


def test_ci_fails_when_the_pointer_moves_onto_a_leak(ci_lab: CiLab) -> None:
    base = ci_lab.lab.git("rev-parse", "HEAD")
    move_pointer(ci_lab, "built by adaramir\n")
    result = ci(ci_lab.lab, base)
    assert result.code == 1, result
    assert "change.txt:1: adaramir" in result.out


def test_ci_passes_a_clean_moved_pointer(ci_lab: CiLab) -> None:
    base = ci_lab.lab.git("rev-parse", "HEAD")
    move_pointer(ci_lab, "a clean change\n")
    result = ci(ci_lab.lab, base)
    assert result.code == 0, result
    assert "summary: 0 findings" in result.out


def test_ci_refuses_a_missing_base_and_a_shallow_lab(
    ci_lab: CiLab, tmp_path: Path
) -> None:
    assert ci(ci_lab.lab, "1" * 40).code == 2
    ci_lab.lab.write("more.txt", "x\n")
    ci_lab.lab.commit("second")
    shallow = tmp_path / "shallow"
    subprocess.run(
        [
            "git",
            "clone",
            "-q",
            "--depth",
            "1",
            f"file://{ci_lab.lab.root}",
            str(shallow),
        ],
        env=GIT_ENV,
        check=True,
    )
    result = subprocess.run(
        ["bash", str(CI_SCRIPT), "HEAD~1"],
        cwd=shallow,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2, result
    assert "shallow" in result.stderr


def test_two_occurrences_on_one_line_are_two_findings(
    repo: Repo, words: Path, allowed: Path
) -> None:
    repo.write("a.txt", "srv1 then srv1 again\n")
    repo.commit("twice")
    result = guard(repo.root, words, allowed, "--tree")
    assert "summary: 2 findings in 1 files" in result.out, result
