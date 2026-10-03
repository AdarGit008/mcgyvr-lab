# 2026-10-03 social live validation, phase B (hub + both rigs)

The full unmerged hub stack, run on the VPS against the owner's two rigs with
the real rig agent. Phase A (hub only, no GPU) is lab PR #49,
`records/evidence/2026-10-03-social-live-a/` on branch `live-a`.

```
 client (VPS, instruments/) --http--> hub 100.119.117.59:18765 (VPS, Tailscale only)
                                        ^  websocket per rig, through `ssh -R` loopback forwards
               +------------------------+------------------------+
       srv1 "head-rig" (head-owner)                     srv2 "worker-rig" (worker-owner)
       2x RTX 3060 12 GB, roles [head],                 1x GTX 1660 SUPER 6 GB, roles [worker]
       models_dir models.bak/dense                      tensor cache e2e/data/rpc-cache
               +---- WireGuard in the tunnel containers, path "lan" 192.168.1.144 <-> .167 ----+
```

NAT traversal from outside was **not** tested. UDP 3478-3496 is closed by the
VPS firewall, so `MCGYVR_HUB_STUN_HOST` and `MCGYVR_HUB_RELAY_HOST` in `hub.env`
point at the Tailscale address. Both rigs are on the same LAN, and every split
unit took the `lan` path (`08-32b-load.txt`, `wg show endpoints`).

## Heads used

| What | Commit |
|---|---|
| hub `origin/web-feed` (PR #13, the stack tip; contains #4 #5 #8 #7 #9 #10 #11 #12, #6 and web-home #2) | `dc2317ec1df17682c23d3eea37fa647552472b5f` |
| hub local `live-validation` in `/home/adaramir/claude/mcgyvr-hub-live`, reset to the above (was `ec0f220`, phase A's merge; never pushed) | `dc2317ec1df17682c23d3eea37fa647552472b5f` |
| product `origin/ladder-relief-rungs` (PR #568; contains #566 `35d62c39`, #564 `11415cc6`) | `12fa907c1d1b143b91670e06e1ff451d6fc5fd01` |
| agent version reported by both rigs | `0.0.1.dev1371+g12fa907c1` |
| tunnel image built from that head | `mcgyvr-tunnel:e072940be18f` (alpine 3.22 + wireguard-go, wg, nft, iproute2, python3 3.12.15) |
| lab base `origin/mcgyvr-social` | `cf53dc3b8cbbd7bd7fce58234327d80034ba4118` |
| demo driver used (`tools/demo` with `HUB_ONLY`, not on this branch) | lab `live-a` `abd5738050bd7cc46caba84e14aadd0ac61ac8fe` |

On the rigs, `~/mcgyvr-pool-tmp/product` was moved from detached `5cb7910b`
to the local branch `ladder-relief-rungs`. This came from an incremental bundle,
`~/mcgyvr-pool-tmp/product-live-b.bundle` (0.5 MB). Then
`uv sync --frozen --reinstall-package mcgyvr` ran with the existing
`uv-cache`/`uv-python`; the dependencies did not change.

## Result

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Register both rigs via the agent (pool mode), tunnel image, both online with cards, `rig joined` INFO lines | **PASS** | `01-tunnel-image.txt`, `02-hub-up.txt`, `03-rigs-join.txt` |
| 2 | Curated list 8B (prio 1, min 1) + 32B (prio 2, min 1); the fleet starts units on its own; one-rig 8B unit; split 32B | **PASS**, one after the other: rigs are claimed whole, so the 8B took both srv1 cards | `05-*`, `07-*`, `08-32b-load.txt`, `09-chat-32b.txt` |
| 3 | Chat non-stream/stream on each unit; not-running refusal; `402`; ledger (spend, earn split by layers, standby, starter) | **PASS** | `05-chat-8b-and-credits.txt`, `06-credits-402.txt`, `09-chat-32b.txt`, `04-hub-restart-standby-flush.txt` |
| 4a | Worker agent stopped mid-stream: hold, then resend/503 per #9 | **FAIL** (works partly): the stream is cut correctly, but held requests got **502**, never a hold up to `FLEET_HOLD_S` | `10-fleet-change-1/`, `11-fleet-change-2/` |
| 4b | Agent back within the 30 s grace: reconnect, else replacement | **PASS** for a link blip (unit resumed, stream finished). A SIGTERMed agent comes back without its session, so a reload follows (bug 1) | `12-link-blip/`, `10-fleet-change-1/` |
| 4c | 32B max to 0: drain and retire; `fleet replan` | **PASS** (needs `--copies 0 --max 0`; `--max 0` alone is refused) | `13-drain-retire/` |
| 4d | 45 s worker-silence limit vs the 32B cold load | **PASS**: not tripped, cold or cached | `11-fleet-change-2/`, `08-32b-load.txt` |
| 5 | Crew: create, join by code, rig to crew mode + `rigs crew`, owner lists the 8B, crew unit, crew chat, non-member refused, no credits | **PASS** | `14-crew-setup.txt`, `15-crew-chat.txt` |
| 6 | Hitchhike 6a: offer, ride on, match, `/me/rungs`, `rig rungs sync` writes `relief.yaml`, ride -> `503 hitchhike_not_served_yet` | **PASS** | `16-hitchhike.txt`, `17-rungs-sync.txt` |
| 7 | Web: both users signed in, feed, profile balance/prices, `/me/hitchhike`, `/me/crews/{id}`, `/me/rigs` crew choice, landing | **PASS** (23/23 + forms) | `18-web/` |
| 8 | Tear-down: rigs as found, hub left running | **PASS** | `20-teardown.txt`, `21-rigs-clean.txt` |

## Timings

| Unit | Load (start -> model loaded) | Start -> ready | First request (warm-up) | Head tok/s | Client stream |
|---|---|---|---|---|---|
| 8B `Qwen3-8B-Q4_K_M` one-rig on srv1 (`-dev CUDA0,CUDA1 -ts 18,19`, ctx 12288) | 32 s (08:16:50 -> 08:17:22); 28 s after the hub restart | ~60 s for the crew unit (08:56:54 -> 08:57:53) | 3.79 s vs 3.11 s for the next one (non-stream, 128 tok) | 61 | TTFT 1.10 s; 34-45 tok/s delivered |
| 32B `Qwen2.5-Coder-32B-Q5_K_M` split srv1 2x3060 + srv2 1660S (`-ts 27,26,12`, LAN), worker cache warm | 55 s (08:33:48.9 -> 08:34:44.1) | 98 s (08:33:42 -> 08:35:20) | 10.23 s vs 9.13 s (prompt 20 tok 201 ms vs 85 ms) | 11.6 | TTFT 1.11 s; 12.6-12.8 tok/s |
| same, worker cache moved aside (cold) | 93 s (08:49:49.9 -> 08:51:23.0) | 136 s (08:49:43.5 -> 08:51:59.4) | - | - | - |

Every unit spends about 36 s between "model loaded" and the hub's "ready"
(CUDA graph warm-up on the worker, e.g. 08:35:16).

**Fleet change** (`FLEET_HOLD_S`=180, grace 30 s, `FLEET_RETRY_S`=120):

| Run | What the client saw | Timing |
|---|---|---|
| 1: SIGTERM the srv2 agent mid-stream, restart at once | Stream: 79 tokens, then `data: {"error":{"message":"the response was cut off","code":"session_ended"}}`, no `[DONE]`, no resend. A request sent during the hold got **502** `session_failed` "the pool session failed (busy)" | rig left +0.95 s, agent back +7.2 s (within grace), but the unit fails `member_lost_session`, the heir starts and fails `busy` 2.1 s later, waiter refused at 5.53 s; serving again after **3 min 47 s** (120 s of it the busy rest) |
| 2: same, agent away 60 s, worker cache moved aside | Stream: silent for 29.4 s after the last token, then the same cut-off chunk. Held request: **502** `session_failed (agent_gone)` after 27.8 s | at grace end (30.0 s): `failed code=agent_gone` -> `lost why=no_heir`; agent back +67 s -> new unit at once, cold ready 136 s later |
| 3: 14 s link blip (srv2's ssh forward closed) | In-flight stream finished normally (9.76 s). A held request from head-owner was **served** after the resume (16.64 s wall) | rig left -> held -> joined 13.6 s later -> `resumed` |
| drain | In-flight and newly admitted requests finished; then `stopped reason=retired` | `retiring` 5.5 s after `fleet replan` (`in_flight=1`), stopped 1.7 s later |

**Credits** (prices per 1000 tokens, set with `models set --price-in/--price-out`):

- 8B priced at 1/2: a spend of 0.279 = 23x1 + 128x2 (/1000).
- 32B priced at 2/4: a spend of 0.5, split 0.414063 to head-owner and 0.085937 to worker-owner (53/64 and 11/64 of the layers). The `credits earn split` log lines show the same shares.
- Starter: 100 per owner on first lend; not granted again after the hub restart.
- Standby:
  - At shutdown it flushed 0.040277 (2 cards x 12 min x 0.1/card-hour) and 0.02.
  - Trickles of 0.006666 / 0.003333 followed every 120 s. This interval is `MCGYVR_HUB_CREDITS_STANDBY_FLUSH_S=120`, added to `hub.env` for this test; the default 3600 would show nothing for an hour.
- 402 at a balance of 0.1 (needed about 0.305) after a `credits grant -99.224666`, which was given back afterwards.
- Crew chats wrote no `spend`/`earn_work` entries.

## Bugs and findings, by severity

1. **High. A rig is reused before its agent has finished the last teardown: the start fails `busy`, then 120 s rest.**
   - It happened three times: the 8B->32B swap, the first start after a hub restart, and the heir in fleet change run 1, where it turned a held request into a 502.
   - Hub side: `_teardown` awaits `SessionStop`, then `_forget` frees the rigs with `_changed()` (`src/mcgyvr_hub/pool_sessions.py:2207-2236`).
   - Agent side: it still refuses with `BUSY "this rig is in another session"` while the old session is live (product `src/mcgyvr/rig/session.py:568-571`).
   - The failed start rests the rigs `fleet_retry_s` (`pool_sessions.py:2146-2148`).
   - I infer the order from the logs (the start comes 0.1 s after `stopped`, the refusal ~2 s later); I did not trace it frame by frame.
2. **High. Restarting the hub leaves its units running on the rigs.**
   - uvicorn closes every websocket with 1012 (`uvicorn/protocols/websockets/websockets_impl.py:155`) before the lifespan exit runs `sessions.shutdown()` (`src/mcgyvr_hub/app.py:49-52`).
   - The `hub_shutdown` stop (`pool_sessions.py:470`) therefore reaches no agent.
   - The new hub's first start failed `busy` (bug 1); the unit was back after 2.5 min.
3. **Medium. Held requests fail at the end of the grace when the unit has no heir.**
   - `_reload` -> `lost why=no_heir` ends the queue (`pool_sessions.py:1161-1179`), so `FLEET_HOLD_S`=180 never applies with two rigs.
   - In run 2 the worker came back 37 s later and the model was reloaded, but the waiter had already got a 502.
   - In-flight streams sit silent for the whole 30 s grace before the cut-off (the head is blocked on the dead RPC peer).
4. **Medium (product). About 1 s of added latency and bursty streams.**
   - The agent's pump waits up to `RECEIVE_SLICE_S = 1.0` (`src/mcgyvr/rig/agent.py:72`). Whether it waits is decided before blocking (`agent.py:419-421`), and `Outbox.put` does not wake it.
   - Result: every request gets ~1.10 s to its first byte. Streams come in runs of 3-4 chunks, then stall 0.7-1.3 s (`05b-stream-8b-trace.txt`).
   - The 8B is delivered at 34-45 tok/s against the head's 61. One frame per token under `FRAMES_PER_SECOND` 49 (`agent.py:70`) also caps it.
5. **Low. A user whose only rig is away gets 404 `model_not_found` "Running now: nothing you can use".** They should get 403 `not_giving`, as a user with no rig does (`pool_sessions.py:1459`; `12-link-blip/C2-*`).
6. **Low. With `X-Mcgyvr-Scope: crew`, `/v1/models` shows pool `pricing` for the crew model** (`src/mcgyvr_hub/api/openai.py:123-128`), though crew requests are free (`15-crew-chat.txt`).
7. **Low. The feed reports every unit start, even ones that failed at once (`busy`), and has no item for failed or lost units.**
   - Starts are written at `pool_sessions.py:1087,1217`; a stop only at `:2205`.
   - Result: 5 "The pool started a unit of 32B" against 1 "stopped" (`18-web/head-owner/feed.txt`).
8. **Low. Adding a crew model through the API does not poke the fleet.** The crew unit started 60 s later, on the tick (`src/mcgyvr_hub/api/crews.py:128-150`).
9. **Low. The hub's log lines have no timestamps** (uvicorn's format, `src/mcgyvr_hub/cli.py:68-78`). `22-hub-log-timestamped-from-0836.txt` was stamped on arrival by a `tail -F`.
10. **Low. `rig joined ... again=False` even for a rejoin within the grace whose unit then resumed** (`src/mcgyvr_hub/api/agent_channel.py:137`).
11. **Design note, not a bug.** Rigs are claimed whole: a one-rig 8B takes both 3060s (`-ts 18,19`), and the 32B cannot start beside it. The 32B ran only after the 8B was set to 0/0.
12. **Design note, not a bug.** A rung's `address` is the base URL of the request that asked (`http://100.119.117.59:18765/v1` via the tailnet, `http://127.0.0.1:18765/v1` in the rig's sync), because `MCGYVR_HUB_PUBLIC_URL` is empty.

Nothing on the rigs that was not ours was touched. Pre-existing, left alone:
- srv1: exited containers `mcgyvr-lcpp` and `vllm-nemotron-4b`.
- srv2: exited containers `vllm-7b-coder`, `vllm-nemotron-30b` and `vllm-nemotron-4b`.
- Phase A's stray VPS process 2915816 is gone.

## Left running, and how to stop it

- **Hub, running on the VPS**:
  - pid in `~/.local/state/mcgyvr-demo/hub.pid`, from `/home/adaramir/claude/mcgyvr-hub-live` (`live-validation` = `dc2317e`).
  - Log `~/.local/state/mcgyvr-demo/hub.log`; db `hub.db` (alembic 0012).
  - Bootstrap users and rigs in `secrets.json`, the crew id in `live-b-crew.json`.
  - `hub.env` (0600) now has STUN/relay on 100.119.117.59, `ADMIN_HANDLES=live-b-admin`, and `CREDITS_STANDBY_FLUSH_S=120`. Delete that last line for the default.
- **State it was left in**:
  - Both rigs are in pool mode and offline.
  - Pool list: 8B 0/0 (1/2), 32B 1/1 (2/4).
  - Crew `live-b-crew` (owner head-owner, member worker-owner) with the 8B 1/1.
  - head-owner's offer on head-rig (inactive: the rig is not in hitchhike mode).
  - worker-owner has ride on.
- **Stop it** (no ssh): from the `live-a` tree, `HUB_ONLY=1 tools/demo/demo-down`, or `kill -TERM $(cat ~/.local/state/mcgyvr-demo/hub.pid)`.
- **To try it with the rigs**: `HUB_REPO=/home/adaramir/claude/mcgyvr-hub-live BIND=100.119.117.59 tools/demo/demo-up` from the `live-a` tree.
  - It re-opens the tunnels and runs `rig run` from the new credentials, and the 32B starts within a minute.
  - The agent rebuilds `mcgyvr-tunnel:e072940be18f` (~9 s) on the first session.
- **Rigs**:
  - No agent, container, llama or rpc process, and no forwarded port.
  - `docker images -a` is identical to the baseline: the tunnel image this run built was removed.
  - `~/mcgyvr-pool-tmp` is in place:
    - The product is on `ladder-relief-rungs`, with `product-live-b.bundle` beside it.
    - `e2e/home/rig-credentials.json` is for this hub. The 2026-10-02 credentials, `agent.log` and `rig-state.json` are kept as `*.2026-10-02-aside`.
    - srv2's `e2e/data/rpc-cache` is the 2026-10-02 one again; the copy re-filled during the cold-load run was removed.
    - srv2 has `e2e/rider-setup/` (fleet.yaml, policy.yaml, relief.yaml) from item 6.
- The phase A state is kept as `~/.local/state/mcgyvr-demo.2026-10-03-live-a-aside`.

## Files

- `instruments/`: `hub.py` (client, redaction), `chat.py`, `watch.py`, `rigwatch.sh`, `fleet_change.sh`, `crew_setup.py`, `hitchhike.py`, `web_walk.py`, `web_forms.py`.
- Numbered files: the commands and their trimmed output, in run order.
- Redactions: keys show as `mh?_<redacted>`, the crew invite code as `<redacted>`, and `hub.env` is never printed.
