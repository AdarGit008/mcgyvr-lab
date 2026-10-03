#!/usr/bin/env python3
"""Pilot P3: play the harness against a local rung over OpenAI chat/completions.

Usage: tool_loop.py BASE_URL MODEL TAG REPO OUT.jsonl [--max-turns N] [--cfg DIR]

The rung is offered four tools (read_file, write_file, bash, grep) and a compact
mcorch-style system prompt; this script executes the rung's tool calls in a
fresh clone of REPO and feeds the results back, until the rung answers with no
tool call or the turn cap is hit. Per turn: wall, prompt/completion tokens,
cached_tokens (prefix reuse), tool calls parsed by the server, unparsed
tool-call-looking text. At the end: did a contract get written, did `mcgyvr run`
get invoked, its result outcome, and whether the repo's accept.py passes.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SYSTEM = """You are mcorch, a local coding agent. You work in the user's repository through tools and finish by answering in plain text with no tool call.

Workflow for a coding request:
1. Look at the repository (grep / read_file) just enough to know the target file and its test command.
2. Write ONE mcgyvr task contract to `contract.yaml` with write_file. Schema (YAML, these keys only):
   id: <letters-digits-dashes>
   task_type: function_implementation | bug_fix | docstring | type_annotation | rename_symbol | format | lint_fix | import_sort | test_scaffold
   task: <what to do, self-contained, addressed to a worker that sees only this contract and the target file>
   target: <one repo-relative file path>
   interface: <the signature(s) the result must expose>
   stop_conditions: [<when the worker must stop and report BLOCKED instead of guessing>]
   acceptance: [<shell command(s) that must pass, e.g. "python accept.py">]
   scope: {allow: [<glob of files the change may touch>]}
   limits: {max_output_tokens: 2048}
3. Validate: bash `mcgyvr contract contract.yaml`. Fix the contract if it is refused.
4. Run: bash `mcgyvr run contract.yaml --repo . --sandbox tempdir --orchestrator mcorch`. The last stdout line is `result: <path>`.
5. Read the result file (read_file on that path). `outcome: accepted` means done; otherwise read `attempts[].findings`, narrow or fix the contract, and run again (at most 2 more times).
6. Finish with a short plain-text summary: the outcome and what changed. Never claim success you did not read from the result file.

Rules: never edit the target file yourself; the worker does. Keep tool arguments exact JSON. One contract at a time."""

TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a file in the repository (or an absolute path the tools returned). Returns its text.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write a file in the repository, creating or replacing it.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command in the repository root. Returns stdout, stderr and the exit code.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "grep", "description": "Search the repository for a regular expression. Returns matching lines with file:line.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "description": "file or directory, default the repository root"}}, "required": ["pattern"]}}},
]


def run_tool(name: str, args: dict, work: Path, env: dict) -> str:
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
            cmd = args["command"]
            # the harness jails bash to the repository: any cd out of it, any
            # absolute path outside the repo or the result/journal dirs, is refused
            allowed = (str(work), "/tmp/claude-1000/", "/home/adaramir/.local/state/mcgyvr")
            for m in re.findall(r"(?<![\w.-])(/[\w./-]*)", cmd):
                if not m.startswith(allowed) and not m.startswith(("/dev/null", "/usr/bin", "/bin")):
                    return f"error: refused by the harness — path {m} is outside the repository"
            if re.search(r"\bcd\s+(\.\.|~)|\brm\s+-[a-z]*r", cmd):
                return "error: refused by the harness — leaves or destroys the repository"
            r = subprocess.run(cmd, shell=True, cwd=work, capture_output=True, text=True, timeout=900, env=env)
            return f"exit {r.returncode}\nstdout:\n{r.stdout[-6000:]}\nstderr:\n{r.stderr[-3000:]}"
        if name == "grep":
            target = args.get("path") or "."
            r = subprocess.run(["grep", "-rnE", "--exclude-dir=.git", args["pattern"], target], cwd=work, capture_output=True, text=True, timeout=60)
            return (r.stdout or "(no match)")[-6000:]
        return f"error: unknown tool {name}"
    except Exception as exc:
        return f"error: {type(exc).__name__}: {exc}"


def post(url: str, body: dict) -> tuple[dict, float]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=3600) as resp:
        doc = json.loads(resp.read())
    return doc, time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("model")
    ap.add_argument("tag")
    ap.add_argument("repo")
    ap.add_argument("out")
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--cfg", default="")
    args = ap.parse_args()
    repo = Path(args.repo)
    truth = json.loads((repo / ".truth.json").read_text())
    work = Path(args.out).parent / "p3work" / f"{repo.name}-{args.tag}"
    if work.exists():
        shutil.rmtree(work)
    work.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", str(repo), str(work)], check=True)
    (work / ".truth.json").unlink(missing_ok=True)
    env = dict(__import__("os").environ)
    if args.cfg:
        env["MCGYVR_CONFIG"] = args.cfg
    # mcgyvr on PATH: the product venv
    mc = "/tmp/claude-1000/-home-adaramir/15b6132f-a502-4a0c-9d7f-4c7b9b894f37/scratchpad/wt/mc-run/.venv/bin"
    env["PATH"] = mc + ":" + env["PATH"]
    prompt = truth["task"] + f"\n\nThe tests are `{' && '.join(truth['acceptance'])}`."
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    url = args.base_url.rstrip("/") + "/v1/chat/completions"
    turns = []
    tools_used = []
    unparsed = 0
    bad_args = 0
    contract_written = False
    runs = 0
    outcomes = []
    final = None
    t_all = time.perf_counter()
    for turn in range(args.max_turns):
        body = {"model": args.model, "messages": messages, "tools": TOOLS, "tool_choice": "auto", "temperature": 0.0, "max_tokens": 4096, "stream": False}
        try:
            doc, wall = post(url, body)
        except Exception as exc:
            turns.append({"turn": turn, "error": f"{type(exc).__name__}: {exc}"[:300]})
            break
        usage = doc.get("usage") or {}
        msg = doc["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        rec = {"turn": turn, "wall_s": round(wall, 2), "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"), "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"), "n_calls": len(calls), "finish": doc["choices"][0].get("finish_reason"), "content_head": content[:160]}
        if not calls and re.search(r"<tool_call>|\"name\"\s*:\s*\"(read_file|write_file|bash|grep)\"", content):
            unparsed += 1
            rec["unparsed_tool_text"] = True
        turns.append(rec)
        messages.append({"role": "assistant", "content": content or None, "tool_calls": calls} if calls else {"role": "assistant", "content": content})
        if not calls:
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
            tools_used.append(name)
            result = run_tool(name, a, work, env) if a or name in ("grep",) else "error: tool arguments were not valid JSON"
            if name == "write_file" and a.get("path", "").endswith((".yaml", ".yml")):
                contract_written = True
            if name == "bash" and "mcgyvr run" in a.get("command", ""):
                runs += 1
                m = re.search(r"result: (\S+)", result)
                if m and Path(m.group(1)).is_file():
                    outcomes.append(json.loads(Path(m.group(1)).read_text()).get("outcome"))
                else:
                    outcomes.append("no_result")
            rec.setdefault("calls", []).append({"name": name, "args_head": json.dumps(a)[:200], "result_head": result[:200]})
            messages.append({"role": "tool", "tool_call_id": c.get("id", f"call_{turn}"), "name": name, "content": result})
    accept = subprocess.run((truth.get("acceptance") or ["python -B accept.py"])[0], shell=True, cwd=work, capture_output=True, text=True, timeout=120)
    target_changed = subprocess.run(["git", "status", "--porcelain", truth["target"]], cwd=work, capture_output=True, text=True).stdout.strip() != ""
    summary = {
        "tag": args.tag, "repo": repo.name, "turns": len(turns), "wall_total_s": round(time.perf_counter() - t_all, 1),
        "tools_used": tools_used, "unparsed_tool_text_turns": unparsed, "bad_args": bad_args,
        "contract_written": contract_written, "mcgyvr_runs": runs, "run_outcomes": outcomes,
        "accept_passes": accept.returncode == 0, "target_changed": target_changed,
        "finished_plain": final is not None, "final_head": (final or "")[:300],
        "max_prompt_tokens": max((t.get("prompt_tokens") or 0) for t in turns) if turns else None,
        "sum_prompt_tokens": sum((t.get("prompt_tokens") or 0) for t in turns),
        "sum_cached_tokens": sum((t.get("cached_tokens") or 0) for t in turns),
        "ttft_proxy_wall_s": [t.get("wall_s") for t in turns],
        "turn_records": turns,
    }
    with open(args.out, "a") as f:
        f.write(json.dumps(summary) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "turn_records"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
