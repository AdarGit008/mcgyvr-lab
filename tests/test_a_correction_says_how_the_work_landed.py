# The lab's copy. The tests of this file that are the product's were removed
# here; they remain in the product's copy of this file.
"""A correction says how the work landed, and the reader shows it end to end.

A row nothing corrects reads ``uncorrected`` forever — including the row of an
attempt the gate accepted and the operator committed. A journal that cannot say
whether a rung's answer was any good is a journal that can be counted and never
learned from, which is the whole reason the text is kept beside the row.

``mcgyvr run`` corrects (:func:`mcgyvr.telemetry.correct`). After the climb,
every attempt row gets the verdict the ladder gave it — ``passed``, ``failed`` —
with the gate's finding lines as the detail of a failure, so the journal answers
*why* without the gate being run again. Then the accepted attempt gets a second
correction saying how the work finally landed: ``committed`` with the commit on
the branch, or ``not_committed`` when the default left the change in the working
tree. ``fold`` is latest-wins in file order, so the folded outcome is the
landing and the raw lines keep the verdict underneath it.

And the reader is wired through: ``tools/live/index.py`` builds a table whose
``outcome`` column carries the folded word and whose ``session_file`` column
carries the transcript, and ``tools/live/review.py --outcome committed``
shows exactly the attempt that was, while ``--outcome uncorrected`` shows
none — the word on the screen is the word that selects it.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests import livejournal as lj

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "tools" / "live" / "index.py"
REVIEW = REPO / "tools" / "live" / "review.py"


def _tool(tool: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(tool), *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=120,
    )


def test_the_index_and_the_review_show_the_landing_end_to_end(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lj.scripted(monkeypatch, lj.GOOD_REPLY)
    repo = lj.make_repo(tmp_path / "repo")
    journal = tmp_path / "journal"
    config = lj.make_config(tmp_path / "mcgyvr.yaml", journal_dir=journal)
    contract = lj.make_contract(tmp_path / "impl.yaml")
    assert lj.main(lj.run_args(contract, repo, config, "--commit")) == 0
    transcript = home / ".claude" / "projects" / "-home-someone-somewhere" / "s1.jsonl"

    built = _tool(INDEX, str(journal))
    assert built.returncode == 0, built.stderr
    db = sqlite3.connect(journal / "index.sqlite")
    try:
        rows = db.execute(
            'SELECT outcome, session_file, task_type, latency_s FROM "attempts"'
        ).fetchall()
    finally:
        db.close()
    assert rows == [("committed", str(transcript), "function_implementation", 0.0)], (
        rows
    )

    shown = _tool(REVIEW, str(journal), "--outcome", "committed")
    assert shown.returncode == 0, shown.stderr
    assert "outcome=committed" in shown.stdout, shown.stdout
    assert f"session={transcript}" in shown.stdout, shown.stdout
    assert "1 of 1 attempts shown" in shown.stderr, shown.stderr

    none = _tool(REVIEW, str(journal), "--outcome", "uncorrected")
    assert none.returncode == 0, none.stderr
    assert "0 of 1 attempts shown" in none.stderr, none.stderr
    assert "===" not in none.stdout
