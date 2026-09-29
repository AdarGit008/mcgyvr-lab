# The lab's part of a split test file. The tests of this file that are the
# product's were removed here; they remain in the product's file at this path.
"""No Ollama. Not fixed, not exempted — removed, and the tree says so.

The code that served Ollama is archived under ``archive/forensic-ollama/`` and is
not in the product.

What must be observably true: nothing in ``src/`` or ``tools/`` can dispatch to,
probe, detect, propose, or configure an Ollama backend. A protocol nobody can
reach is not "supported", it is a second path through every dispatch decision
that no test of the live ladder ever exercises.

**The ban is on the capability, not on the word.** A sweep for ``\bollama\b`` in
``src/`` and ``tools/`` would go green only by deleting things that are true: the
pointers to the archive that the last test in this file *requires* be findable, and
the provenance of measurements actually taken on that backend. A record of where a
number came from is not support for a backend. So a line whose only mention is
a citation is allowed, and everything operational is not.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


OLLAMA = re.compile(r"\bollama\b", re.IGNORECASE)

#: A mention that is a citation rather than a capability: a pointer into the
#: archive, or the provenance of a measurement (an issue number, a CAV
#: study id, or a dated reading). These are records; deleting them to satisfy
#: a word-ban would make the record false.
CITED = re.compile(
    r"archive/forensic-ollama|#\d{2,}|CAV-\d+|\b20\d\d-\d\d-\d\d\b",
    re.IGNORECASE,
)

#: Operational: the backend named as something the product talks to, rather
#: than something it once measured. An identifier, a config value, a unit
#: file, a daemon command. None of these can be provenance — a dispatch
#: branch, an env var the daemon reads or a CLI verb is a capability wherever
#: it appears — so they are flagged without consulting the citation window.
OPERATIONAL = re.compile(
    r"OLLAMA_[A-Z_]+"  # env the daemon reads
    r"|Protocol\.OLLAMA"  # the dispatch branch
    r"|OllamaRunner"  # the client
    r"|[\"']ollama[\"']"  # a config value or a dict key
    r"|ollama\.service"  # the unit
    r"|/api/(tags|generate)"  # the native endpoints
    r"|\bollama (serve|pull|run|list)\b",  # the CLI
    re.IGNORECASE,
)

#: An ADDRESS, which is operational in a live config and provenance in a dated
#: record — so unlike :data:`OPERATIONAL` it is read against the citation
#: window like any other mention.
#:
#: The port was in ``OPERATIONAL`` and that was wrong in one direction that
#: matters. ``tools/bench/strata.json`` is an append-only measurement record
#: whose own doctrine is "a re-assignment is a new dated block appended to
#: `blocks`, never an edit of an old one"; every block carries the endpoint the
#: sweep was pointed at, and every block carries a ``date``. Editing those to
#: satisfy a port ban would make the record say a sweep ran somewhere it did
#: not — the failure this file's own docstring says a word-ban causes.
#:
#: Narrow on purpose. A live config that dialled this port would also name the
#: backend as a value (``"api": "ollama"``) or reach it through a branch, and
#: both of those stay in :data:`OPERATIONAL` where no citation excuses them.
ADDRESS = re.compile(r":11434")


def _lines(root: Path, *suffixes: str) -> list[str]:
    """Operational mentions only. A cited one is a record and is left alone.

    The citation is looked for in a small window around the line rather than on
    it, because provenance is written as a sentence: "…reproduces on the serving
    stack (#167 arm B: … through the same instrument on Ollama)" carries its
    reference two lines above the mention. Judging line by line would call that
    an operational use and demand the record be deleted.
    """
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in suffixes or not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            named = OLLAMA.search(line) or ADDRESS.search(line)
            if not named and not OPERATIONAL.search(line):
                continue
            if OPERATIONAL.search(line):
                found.append(f"{path.relative_to(REPO)}:{index + 1}: {line.strip()}")
                continue
            window = "\n".join(lines[max(0, index - 3) : index + 4])
            if CITED.search(window):
                continue
            found.append(f"{path.relative_to(REPO)}:{index + 1}: {line.strip()}")
    return found


def test_the_tools_carry_no_ollama() -> None:
    """The bench, the rig drivers and the journal readers, on the same rule.

    ``tools/runs/hosts.json`` is the sharpest of these: it declares three
    ``ollama.service`` environment settings and a ``systemctl restart ollama``,
    against a daemon that is now masked on the only rig that ran it.
    """
    remaining = _lines(REPO / "tools", ".py", ".json", ".md", ".sh")
    assert not remaining, (
        f"{len(remaining)} lines still name Ollama in the tools:\n"
        + "\n".join(remaining[:20])
    )


def test_the_reasoning_is_kept_where_it_can_be_read() -> None:
    """Removal is not deletion. CAV-01's finding outlives the backend it was about.

    ``#164`` is the measurement that decided asking and dispatching are separate
    questions, and that conclusion survives Ollama. It belongs in the archive
    with the code it justified, not in a commit message nobody greps.
    """
    archive = REPO / "archive" / "forensic-ollama"
    assert archive.is_dir(), (
        "archive/forensic-ollama/ does not exist; the removed code and the "
        "measurement that justified it must be readable after the removal"
    )
    readme = archive / "README.md"
    assert readme.is_file(), "the archive must say what was removed and why"
    text = readme.read_text(encoding="utf-8")
    assert "164" in text and "CAV-01" in text, (
        "the archive must carry the measurement that decided the design "
        "(#164, CAV-01), or the next reader repeats the experiment"
    )
