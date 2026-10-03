#!/usr/bin/env python3
"""Steps 6 and 7: play the harness against the rung; price the context.

    tool_loop.py LABEL PORT MODEL REPOS_DIR WORK_DIR [--max-turns N]
    tool_loop.py LABEL PORT MODEL --ctx-ladder 4096,16384,32768,65536

Under the door only. The rung is offered the harness's four tools (read_file,
write_file, bash, grep) over OpenAI chat/completions with `tools`, a compact
mcorch system prompt (~700 tokens), and the request; this driver executes the
rung's tool calls in a fresh clone of each repo under REPOS_DIR and feeds the
results back until the rung answers with no tool call or the turn cap. The
engine parses the tool calls (llama.cpp: --jinja and the GGUF's template;
vLLM: --enable-auto-tool-choice --tool-call-parser), so a tool call the
engine did not parse but the text shows is counted as `unparsed`.

Rows, tab-separated `host label kind k=v...`:

  TURN   one request: turn, wall_s (TTFT-dominated: the replies are short),
         prompt_tokens, completion_tokens, cached_tokens (the engine's own
         prefix-reuse count), n_calls, finish, unparsed
  LOOP   one repo: turns, wall_total_s, tools (the sequence), unparsed,
         bad_args, contract_written, runs (`mcgyvr run` invocations),
         outcomes, accept_passes (the repo's own accept.py after the loop),
         target_changed, finished_plain, max_prompt_tokens, sum_cached
  CTX    one rung of --ctx-ladder: tokens (as the server counted them),
         cold_wall_s (a transcript of that size never seen), warm_wall_s (the
         same transcript plus one short tool turn), cached_tokens on the warm
         call, tok_per_s = tokens / cold_wall_s (prompt processing)

The repos come from make_repos.py (a .truth.json beside each). With
MCGYVR_CONFIG exported by the step, `mcgyvr run` inside a bash tool call lands
on the config the step wrote (orch_modes.write_config), so the rung's worker
is the same local unit — the skill flow on a local model.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

try:
    from mcgyvr.serving import gatelib
except ImportError:
    print(
        "tool_loop: mcgyvr.serving.gatelib will not import — this driver runs "
        "under the door, python -m mcgyvr.serving.run",
        file=sys.stderr,
    )
    sys.exit(2)
gatelib.door_required("tool_loop")
RUN_ID = os.environ.get("RUN_ID", "")
if not RUN_ID:
    print(
        "tool_loop: RUN_ID is unset — this driver is started by the door, "
        "python -m mcgyvr.serving.run, never bare",
        file=sys.stderr,
    )
    sys.exit(2)
H = os.environ.get("RUN_HOST", "")
if not H:
    print(
        "tool_loop: RUN_HOST is unset — the door exports it (gate 5)", file=sys.stderr
    )
    sys.exit(2)

REPO = Path(os.environ.get("RUN_ROOT") or Path(__file__).resolve().parents[4])


def tok(value: object) -> str:
    return str(value).replace("\t", " ").replace(" ", "_").replace("\n", "\\n")


def emit(label: str, kind: str, *fields: str, free: str = "") -> None:
    line = "\t".join([H, label, kind, *fields])
    if free:
        line += "\t-- " + free.replace("\t", " ").replace("\n", " ")[:600]
    print(line, flush=True)


SYSTEM = """You are mcorch, a local coding agent. You work in the user's repository
through tools and finish by answering in plain text with no tool call.

Workflow for a coding request:
1. Look at the repository (grep / read_file) just enough to know the target file
   and its test command.
2. Write ONE mcgyvr task contract to `contract.yaml` with write_file. Schema
   (YAML, these keys only):
   id: <letters-digits-dashes>
   task_type: function_implementation | bug_fix | docstring | type_annotation |
     rename_symbol | format | lint_fix | import_sort | test_scaffold
   task: <what to do, self-contained, addressed to a worker that sees only this
     contract and the target file>
   target: <one repo-relative file path>
   interface: <the signature(s) the result must expose>
   stop_conditions: [<when the worker must stop and report BLOCKED instead of
     guessing>]
   acceptance: [<read-only command(s) that pass NOW and must keep passing>]
   demonstration: [<command(s) that FAIL now and must pass after: the task's
     tests>]
   scope: {allow: [<glob of files the change may touch>]}
   limits: {max_output_tokens: 2048}
3. Validate: bash `mcgyvr contract contract.yaml`. Fix the contract if refused.
4. Run: bash `mcgyvr run contract.yaml --repo . --sandbox tempdir
   --orchestrator mcorch`. The last stdout line is `result: <path>`.
5. Read the result file (read_file on that path). `outcome: accepted` means
   done; otherwise read `attempts[].findings`, narrow or fix the contract, and
   run again (at most 2 more times).
6. Finish with a short plain-text summary: the outcome and what changed. Never
   claim success you did not read from the result file.

Rules: never edit the target file yourself; the worker does. Keep tool arguments
exact JSON. One contract at a time."""


def _tool(
    name: str, desc: str, props: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


STR: dict[str, Any] = {"type": "string"}
TOOLS: list[dict[str, Any]] = [
    _tool(
        "read_file",
        "Read a file in the repository (or an absolute path the tools returned). "
        "Returns its text.",
        {"path": STR},
        ["path"],
    ),
    _tool(
        "write_file",
        "Write a file in the repository, creating or replacing it.",
        {"path": STR, "content": STR},
        ["path", "content"],
    ),
    _tool(
        "bash",
        "Run a shell command in the repository root. Returns stdout, stderr and "
        "the exit code.",
        {"command": STR},
        ["command"],
    ),
    _tool(
        "grep",
        "Search the repository for a regular expression. Returns matching lines "
        "with file:line.",
        {
            "pattern": STR,
            "path": {
                "type": "string",
                "description": "file or directory, default root",
            },
        },
        ["pattern"],
    ),
]


def run_tool(name: str, args: dict[str, Any], work: Path, env: dict[str, str]) -> str:
    try:
        if name == "read_file":
            p = Path(args["path"])
            p = p if p.is_absolute() else work / p
            return p.read_text(errors="replace")[:12000]
        if name == "write_file":
            p = work / args["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            return f"wrote {args['path']} ({len(args['content'])} chars)"
        if name == "bash":
            cmd = str(args["command"])
            # the harness jails bash to the repository (pilot P3: a rung ran
            # `cd /tmp && cp -r ./* test_dir/`): any absolute path outside the
            # repo, the run envelope or mcgyvr's state, and any recursive rm or
            # cd out, is refused and the refusal is what the rung reads back
            allowed = (str(work), str(REPO), "/tmp/claude-1000/", "/dev/null")
            for m in re.findall(r"(?<![\w.-])(/[\w./-]*)", cmd):
                if not m.startswith(allowed) and not m.startswith(("/usr/bin", "/bin")):
                    return (
                        f"error: refused by the harness — {m} is outside the repository"
                    )
            if re.search(r"\bcd\s+(\.\.|~)|\brm\s+-[a-z]*r", cmd):
                return (
                    "error: refused by the harness — leaves or destroys the repository"
                )
            r = subprocess.run(
                cmd,
                shell=True,
                cwd=work,
                capture_output=True,
                text=True,
                timeout=900,
                env=env,
            )
            return (
                f"exit {r.returncode}\nstdout:\n{r.stdout[-6000:]}"
                f"\nstderr:\n{r.stderr[-3000:]}"
            )
        if name == "grep":
            target = args.get("path") or "."
            r = subprocess.run(
                ["grep", "-rnE", "--exclude-dir=.git", args["pattern"], target],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return (r.stdout or "(no match)")[-6000:]
        return f"error: unknown tool {name}"
    except Exception as exc:
        return f"error: {type(exc).__name__}: {exc}"


def post(url: str, body: dict[str, Any]) -> tuple[dict[str, Any], float]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=3600) as resp:
        doc = json.loads(resp.read())
    return doc, time.perf_counter() - t0


def loop(
    label: str, url: str, model: str, repo: Path, work_root: Path, max_turns: int
) -> None:
    truth = json.loads((repo / ".truth.json").read_text())
    work = work_root / repo.name
    if work.exists():
        shutil.rmtree(work)
    work.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", str(repo), str(work)], check=True)
    (work / ".truth.json").unlink(missing_ok=True)
    env = dict(os.environ)
    acceptance = " && ".join(truth["acceptance"])
    demonstration = " && ".join(truth.get("demonstration") or [])
    prompt = (
        truth["task"]
        + f"\n\nAcceptance (passes now, must keep passing): `{acceptance}`."
        + f"\nDemonstration (fails now, must pass after): `{demonstration}`."
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    tools_used: list[str] = []
    unparsed = bad_args = runs = 0
    contract_written = False
    outcomes: list[str] = []
    final: str | None = None
    max_prompt = sum_cached = 0
    t_all = time.perf_counter()
    turn = 0
    for turn in range(max_turns):
        body = {
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0.0,
            "max_tokens": 4096,
            "stream": False,
        }
        try:
            doc, wall = post(url, body)
        except Exception as exc:
            emit(
                label,
                "TURN",
                f"repo={tok(repo.name)}",
                f"turn={turn}",
                free=f"{type(exc).__name__}: {exc}",
            )
            break
        usage = doc.get("usage") or {}
        msg = doc["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        ptok = usage.get("prompt_tokens") or 0
        max_prompt = max(max_prompt, ptok)
        sum_cached += cached
        looks_like_call = bool(
            re.search(
                r"<tool_call>|\"name\"\s*:\s*\"(read_file|write_file|bash|grep)\"",
                content,
            )
        )
        if not calls and looks_like_call:
            unparsed += 1
        emit(
            label,
            "TURN",
            f"repo={tok(repo.name)}",
            f"turn={turn}",
            f"wall_s={wall:.2f}",
            f"prompt_tokens={ptok}",
            f"completion_tokens={usage.get('completion_tokens', 'na')}",
            f"cached_tokens={cached}",
            f"n_calls={len(calls)}",
            f"finish={tok(doc['choices'][0].get('finish_reason'))}",
            f"unparsed={int(not calls and looks_like_call)}",
            free=content[:120],
        )
        if calls:
            messages.append(
                {"role": "assistant", "content": content or None, "tool_calls": calls}
            )
        else:
            messages.append({"role": "assistant", "content": content})
            final = content
            break
        for c in calls:
            fn = c.get("function", {})
            name = fn.get("name")
            try:
                a = json.loads(fn.get("arguments") or "{}")
                if not isinstance(a, dict):
                    raise ValueError("arguments not an object")
            except Exception:
                bad_args += 1
                a = {}
            tools_used.append(str(name))
            result = (
                run_tool(str(name), a, work, env)
                if a
                else "error: tool arguments were not valid JSON"
            )
            if name == "write_file" and str(a.get("path", "")).endswith(
                (".yaml", ".yml")
            ):
                contract_written = True
            if name == "bash" and "mcgyvr run" in str(a.get("command", "")):
                runs += 1
                m = re.search(r"result: (\S+)", result)
                if m and Path(m.group(1)).is_file():
                    outcomes.append(
                        str(json.loads(Path(m.group(1)).read_text()).get("outcome"))
                    )
                else:
                    outcomes.append("no_result")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": c.get("id", f"call_{turn}"),
                    "name": name,
                    "content": result,
                }
            )
    # the task's own tests: the demonstration when the corpus carries one
    check = (truth.get("demonstration") or truth["acceptance"])[0]
    accept = subprocess.run(
        check,
        shell=True,
        cwd=work,
        capture_output=True,
        text=True,
        timeout=120,
    )
    changed = subprocess.run(
        ["git", "status", "--porcelain", truth["target"]],
        cwd=work,
        capture_output=True,
        text=True,
    ).stdout.strip()
    emit(
        label,
        "LOOP",
        f"repo={tok(repo.name)}",
        f"turns={turn + 1}",
        f"wall_total_s={time.perf_counter() - t_all:.1f}",
        f"tools={tok(','.join(tools_used) or 'none')}",
        f"unparsed={unparsed}",
        f"bad_args={bad_args}",
        f"contract_written={int(contract_written)}",
        f"runs={runs}",
        f"outcomes={tok(','.join(outcomes) or 'none')}",
        f"accept_passes={int(accept.returncode == 0)}",
        f"target_changed={int(bool(changed))}",
        f"finished_plain={int(final is not None)}",
        f"max_prompt_tokens={max_prompt}",
        f"sum_cached={sum_cached}",
        free=(final or "")[:200],
    )


def ctx_ladder(label: str, url: str, model: str, sizes: list[int]) -> None:
    """Prompt-processing cost at mcorch-shaped context: a cold transcript of
    about N tokens (tool results of filler code, unique per rung), then the
    same transcript plus one short tool turn (the prefix-cache case)."""
    rng = random.Random(20261003)
    for n in sizes:
        filler_lines = max(1, (n - 1200) // 12)  # ~12 tokens per filler line
        salt = rng.randrange(10**9)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Inspect the repository (seed {salt}); list the helpers.",
            },
        ]
        chunk: list[str] = []
        i = 0
        while i < filler_lines:
            lines = [
                f"def helper_{salt}_{i + k}(x):\n    return x + {i + k}  # pad"
                for k in range(min(40, filler_lines - i))
            ]
            cid = f"call_{len(chunk)}"
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": cid,
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps(
                                    {"path": f"pkg/mod_{len(chunk)}.py"}
                                ),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": cid,
                    "name": "read_file",
                    "content": "\n".join(lines),
                }
            )
            chunk.append(cid)
            i += 40
        messages.append({"role": "user", "content": "Reply with the single word OK."})
        body = {
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "temperature": 0.0,
            "max_tokens": 4,
            "stream": False,
        }
        try:
            doc, cold = post(url, body)
        except Exception as exc:
            emit(
                label,
                "CTX",
                f"tokens_asked={n}",
                free=f"cold: {type(exc).__name__}: {exc}",
            )
            continue
        tokens = (doc.get("usage") or {}).get("prompt_tokens") or 0
        messages.insert(
            -1,
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_last",
                        "type": "function",
                        "function": {
                            "name": "grep",
                            "arguments": json.dumps({"pattern": "helper_0"}),
                        },
                    }
                ],
            },
        )
        messages.insert(
            -1,
            {
                "role": "tool",
                "tool_call_id": "call_last",
                "name": "grep",
                "content": "pkg/mod_0.py:1:def helper_0(x):",
            },
        )
        body["messages"] = messages
        try:
            doc2, warm = post(url, body)
        except Exception as exc:
            emit(
                label,
                "CTX",
                f"tokens_asked={n}",
                f"tokens={tokens}",
                f"cold_wall_s={cold:.2f}",
                free=f"warm: {type(exc).__name__}: {exc}",
            )
            continue
        cached = ((doc2.get("usage") or {}).get("prompt_tokens_details") or {}).get(
            "cached_tokens", "na"
        )
        emit(
            label,
            "CTX",
            f"tokens_asked={n}",
            f"tokens={tokens}",
            f"cold_wall_s={cold:.2f}",
            f"warm_wall_s={warm:.2f}",
            f"cached_tokens={cached}",
            f"tok_per_s={tokens / cold if cold else 0:.1f}",
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("port", type=int)
    ap.add_argument("model")
    ap.add_argument("repos", nargs="?")
    ap.add_argument("work", nargs="?")
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--ctx-ladder", default="")
    args = ap.parse_args()
    url = f"http://{H}:{args.port}/v1/chat/completions"
    if args.ctx_ladder:
        ctx_ladder(
            args.label, url, args.model, [int(x) for x in args.ctx_ladder.split(",")]
        )
        return 0
    if not args.repos or not args.work:
        print(
            "tool_loop: REPOS_DIR and WORK_DIR are required without --ctx-ladder",
            file=sys.stderr,
        )
        return 2
    for repo in sorted(Path(args.repos).iterdir()):
        if (repo / ".truth.json").is_file():
            loop(args.label, url, args.model, repo, Path(args.work), args.max_turns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
