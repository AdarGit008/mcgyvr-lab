# 2026-10-03 social live validation, phase A (hub side only)

The unmerged hub stack, deployed as the demo hub on the VPS (`vps`,
Tailscale 100.119.117.59, public 185.245.183.242) and checked without any
GPU. **srv1 and srv2 were not touched** (another team's GPU measurement was
running on them): no ssh, no agent, no image. `demo-up`/`demo-down` got a
`HUB_ONLY=1` mode for this (below).

## Heads used

| What | Commit |
|---|---|
| hub `origin/pool-fleet-change` (PR #9, tip of the stack) | `a4c643769791b9fec601145e2e46b4be72517369` |
| hub `origin/web-home` (PR #2, merged in, not in the stack) | `48ca04cecbf27e482cc023159f154edb2befde72` |
| hub local `live-validation` = merge of the two (never pushed) | `ec0f2201bf1da308cdea96de0212a7b298d33ddb` |
| lab base `origin/mcgyvr-social` | `cf53dc3b8cbbd7bd7fce58234327d80034ba4118` |

**Not validated here:** after this run, `pool-fleet-change` moved on to
`58d15b264329666e7739e8bb08432a14ce46ea64`. It added two commits: `6eb7d41`,
where a held request waits through the load up to `MCGYVR_HUB_FLEET_HOLD_S`, and
`58d15b2`, which keeps the fleet-change tests' timing under load. Together they
touch `pool_sessions.py` and the tests. The deployed hub does not have them.

The rest of the stack (`connect`, `pool-wait-queue`, `pool-fair-order`,
`pool-session-width`, `pool-fleets`, `fix/single-rig-session-connect`) is
contained in the tip; all heads are in `00-build.txt`. The web-home merge
conflicted in `completions.py` and `tests/test_web_pool.py` (Try-it, which
web-home deletes and the queue/fleet-change PRs had touched); resolved by
keeping the stack's code and dropping the Try-it helpers and tests. The hub
gate on the merge: `make check` passed (ruff, format, mypy strict, 1577
tests, build).

## Result

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Deploy as demo hub, fresh state, migrations 0001-0006, health, clean log | **PASS** | `01-demo-up.txt`, `01b-restart-fresh.txt`, `02-health.txt`, `10-hub-log.txt` |
| 2 | Web: sign-up, landing vs home, key shown once, endpoint URL, `/network`, no Try-it, `/pool/plan` 404 user / 200 admin | **PASS** (16/16) | `03-web.txt` |
| 3 | `models add/set/list/remove`, `fleet replan`; `/v1/models` empty; chat gives the documented error, not 500; idle with empty list | **PASS** | `04-models-cli.txt`, `05-v1-api.txt`, `10-hub-log.txt` |
| 4 | Binding responder, relay, latency probe | **PASS** on this host; **not verified from off the host** | `06-udp-host.txt`, `07-udp-docker-vantage.txt`, `08b-stun-probe-live-10s.txt` |
| 5 | Wait queue without a unit: not-running fails fast | **PASS** (all ≤ 0.06 s; 6 concurrent in 0.17 s) | `05-v1-api.txt` |
| 6 | Left running, teardown recorded | hub running | below |

Notes per item:

1. `demo-up --fresh` with `HUB_ONLY=1`, `HUB_REPO=/home/adaramir/claude/mcgyvr-hub-live`,
   `BIND=100.119.117.59`. The fresh `hub.db` reads `alembic_version = 0006`
   with all tables. The hub was restarted once on a fresh db (`01b`) after
   a regex bug in my own web instrument (`03-web-run1-regex-bug.txt`: it took the
   home page's `mhu_<id>_…` key label for a plaintext key; the hub was right).
2. All through the real forms (CSRF, Origin). The admin is `live-a-admin`
   (`MCGYVR_HUB_ADMIN_HANDLES`); a logged-out visitor also gets 404 on `/pool/plan`.
3. CLI errors are clean (duplicate, bad name, max < min, nothing to set, unknown
   name: exit 1/2 with one line). Each `fleet replan` was applied by the running
   hub within ~2 s (`fleet_replans.applied_at`). Chat: `404 model_not_found`,
   "… is not running in the pool, and the pool does not start models on request.
   Running now: nothing you can use." (`own`/`crew` scope: "no rig you can use
   has this model"); the same with the model on the list and no rig. 401/400 for
   no key, bad JSON, bad scope header. The list is left empty. The hub then ran
   13 min with an empty list (01:53-02:06Z, with fleet ticks every 60 s and a
   probe refresh at 300 s). The only new log line came from a
   `hubctl.py share head-rig pool` check: a no-op PATCH, 200. No
   traceback/error/warning anywhere in the log, and RSS was 49 MB (`10-hub-log.txt`).
4. On the VPS: UDP 3478 and 3479 (responder) and 3480 (relay control) listen on
   0.0.0.0; relay allocations use 3481-3496. From three source addresses (public,
   Tailscale, loopback) to both the public and the Tailscale address: an unissued
   token or a malformed request gets **no answer**; relay: bad ticket → silence,
   expired → `refused(expired)`, valid → both sides bound in 3481-3496, packets
   forwarded both ways, third-party and 3000-byte packets dropped, `max_mb=0` ends
   the allocation, a 16-bind burst from one source gets 10 answers. Positive
   responder path and latency probe: two model-less lab agents
   (`tests/natlab/mini_agent.py`, no GPU) on this host as throwaway rigs, one
   bound to the public and one to the Tailscale address. Both responder ports
   answered each, reporting `185.245.183.242:<port>` and `100.119.117.59:<port>`
   (same mapping on both ports, so not symmetric). The admin's plan preview
   started a probe: **0.5 ms, 240.7 Mbit/s, direct (hole-punched), measured**.
   Both throwaway rigs were then deleted (HTTP 204). (`08a`, read after 2 s, still
   showed the estimate; its script is the same with a 2 s wait.)
   **Not verified:** reachability from off the host. Docker as a second vantage
   point was useless (`07`): the host firewall drops all UDP from the docker
   bridge, even to a plain echo server. There is no sudo to read the rules, and
   no other machine was allowed in this phase.
5. No unit exists, so the hold and slot-wait paths (`chat_wait_ready_s` 20,
   `chat_wait_slot_s` 30) are not reached. Every not-running request returned
   in 2-60 ms, none waited for a limit. Held-request behaviour needs a unit (phase B).

## Ports

| Port | Proto | Bound | Who must reach it |
|---|---|---|---|
| 18765 | TCP | 100.119.117.59 (Tailscale only) | browsers and API clients on the tailnet; rigs through `ssh -R` as before |
| 3478, 3479 | UDP | 0.0.0.0 | rigs, at `MCGYVR_HUB_STUN_HOST` = 185.245.183.242 |
| 3480 | UDP | 0.0.0.0 | rigs, relay control at `MCGYVR_HUB_RELAY_HOST` = 185.245.183.242 |
| 3481-3496 | UDP | 0.0.0.0 | rigs using the relay (8 rig pairs at a time) |

For phase B, open UDP 3478-3496 in the VPS firewall (needs root; not done
here), or point `STUN_HOST`/`RELAY_HOST` in `hub.env` at the Tailscale address
and restart the hub. Check from a rig before relying on either.

## Running now, and how to stop it

- Hub pid in `~/.local/state/mcgyvr-demo/hub.pid`, started from the
  worktree `/home/adaramir/claude/mcgyvr-hub-live` (its `.venv`), log
  `~/.local/state/mcgyvr-demo/hub.log`. Settings come from
  `~/.local/state/mcgyvr-demo/hub.env` (0600, holds the relay secret),
  which `demo-up` now sources. Bootstrap users (`head-owner`, `worker-owner`,
  `requester`) and rigs (`head-rig`, `worker-rig`, pool mode, never joined) are in
  `secrets.json` as before. Web users are `live-a-user` and `live-a-admin`;
  their keys are in `live-a-keys.json` (0600).
- **Stop the hub only** (no ssh): `HUB_ONLY=1 tools/demo/demo-down` from this
  lab tree, or `kill -TERM $(cat ~/.local/state/mcgyvr-demo/hub.pid)`.
  Plain `demo-down` also ssh-es to srv1/srv2, so do not run it until the rigs are free.
- **Phase B attaches the rigs:** run `HUB_REPO=/home/adaramir/claude/mcgyvr-hub-live
  BIND=100.119.117.59 tools/demo/demo-up` without `HUB_ONLY` and without
  `--fresh`. It sees the running hub and goes on to the tunnels and agents. Put
  the demo model on the list first with
  `mcgyvr-hub models add Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf --db ~/.local/state/mcgyvr-demo/hub.db`.
- Phase B caution: the rigs may still hold `~/mcgyvr-pool-tmp/e2e/home/rig-credentials.json`
  from the 2026-10-02 hub, whose database is no longer live. If so, `demo-up`
  would run `rig run` with credentials this hub has never seen. Move those files
  aside on the rigs first, so that `demo-up` does a fresh `rig join` against the
  new `head-rig`/`worker-rig` join tokens.
- The previous demo state was moved, not deleted, to
  `~/.local/state/mcgyvr-demo.2026-10-02-aside`.

## Bugs and findings for follow-up

1. Hub, `tests/natlab/integration.py:254` (also :280 and :285) is stale since
   pool-fleets. It never puts `lab-16g.gguf` on the curated list, so the
   general-pool chat gets `404 model_not_found`, and `latest_session()` raises
   `IndexError` at `:235`. The one-machine NAT check no longer runs end to end
   (`09-natlab-integration.txt`). `tests/test_natlab_integration.py` only covers
   its plan-preview helper, so the gate stays green.
2. Hub, `src/mcgyvr_hub/protocol.py:1006` (`describe`): an error with an empty
   `loc` (a body that is not JSON) renders with a leading `": "`:
   `": Invalid JSON: key must be a string …"` (`05-v1-api.txt`). Cosmetic.
3. Hub: nothing of its own reaches the log. It configures no application
   logger, so fleet passes, replans, probes and refusals leave no line, only
   uvicorn's access lines. "Log clean" is therefore weak evidence. A follow-up
   should log fleet decisions and probe outcomes.
4. Lab (fixed on this branch): `demo-up --fresh` removed `hub.db` but left
   `hub.db-wal`/`-shm` behind, which a new database must not inherit.
   It now removes all three.
5. Seen on the VPS, not ours, left alone: pid 2915816 `uv run --no-sync python -`
   in `/home/adaramir/claude/mcgyvr-hub` on a temp db `/tmp/tmpbi2woifv/h.db`,
   running since 2026-10-02 06:55 in state R. It looks like a leftover test hub.
