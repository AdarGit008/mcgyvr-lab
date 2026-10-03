# Desk read: llama.cpp server slots under the pooled head's launch (2026-10-02)

Issue #46, step 0. This is a reading of engine source. Nothing was run on a rig,
and nothing here is a measurement. Every conclusion quotes the source at the
pinned commit. Anything the source did not settle is marked **open**.

## The config this reads

The launch is the pooled head's argv as lab PR #42 recorded it
(`records/evidence/2026-10-02-pooled-e2e/e2e/head-args-3.txt:13` on branch
`mcgyvr-social`, head `cf53dc3b`):

```text
/app/llama-server -m /models/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf -ngl 999 -sm layer -np 1 -c 12288
  -fa on -ctk q8_0 -ctv q8_0 --host 172.17.0.2 --port 8080 --rpc 10.211.0.2:50052
  -dev CUDA0,CUDA1,RPC0 -ts 27,26,12
```

The product writes `-np 1` as a constant (`src/mcgyvr/sandbox/pooled.py:656-657`
on product branch `mcgyvr-connect`, `11415cc6`). `-c` is the hub's `ctx`
(`pooled.py:658-659`, from `HeadSpec.ctx`). The launch passes no `-kvu`, `-nkvo`,
`--cache-ram`, `--cache-reuse`, `--slot-save-path`, `-to` or `--threads-http`,
so each of those takes the engine's default.

## Engine version, and how it was pinned

| what | value | from |
|---|---|---|
| image tag | `llamacpp:b10644-L3-rpc` | PR #42 `live/run3.agent-srv1.out:3` (`lending: head on llamacpp:b10644-L3-rpc`) and `run3.agent-srv2.out:3` (worker); `"runtime"` in the `run3.jsonl` hellos |
| image id | `sha256:c49d9cd3e2d69c7a81305cd8ed15a7bc6cb957e90ff51413a8b864bdb5aa5841` | `records/evidence/2026-09-27-l3-rpc-build/PROVENANCE.txt` (the build record for that tag) |
| llama.cpp commit | `d7a2074112d27649303fa107eb8c94db1ee435f3`, tag `b10644`, build 10644 | the same PROVENANCE, and `llama-server --version` in `srv1-llama-server-version.txt` and `srv2-llama-server-version.txt` beside it |
| source read | `git checkout d7a2074112d2…`: `git tag --points-at HEAD` → `b10644`; `git rev-list --count HEAD` → `10644` | `version-id.txt` |
| local patch | `patch_mmvq.py`, confined to `ggml/src/ggml-cuda/mmvq.cu` | none of the files read below is patched |

The product does not pin the engine image. The owner names it with
`mcgyvr rig share --image` (`src/mcgyvr/rig/sharing.py:8-9`, `src/mcgyvr/rig/verbs.py:550`).
The product fixes only the binaries inside it (`sharing.py:56-57`:
`/app/llama-server`, `/app/ggml-rpc-server`). `src/mcgyvr/sandbox/image.py`
builds task images and never touches the engine image.

**Open:** PR #42 records the tag, not the image id. That the tag still resolved
to `sha256:c49d9cd3…` on 2026-10-02 is not verified, because this read did not
touch the rigs. Every answer below holds for `d7a207411`. It carries over to the
run only if the tag was not rebuilt.

All `path:line` below are llama.cpp at `d7a207411` unless they name the product
or the lab.

---

## Q1. `-np N -c C`: is the context split per slot, or one shared pool?

**At this version, with `-np` given explicitly, the context is split.** Each slot
gets `C/N`, rounded up to a multiple of 256, and gets its own KV stream. The
unified, shared pool is used only with `-kvu` or with `-np` left on auto.

The server's default for `-np` is auto (−1). Auto, and only auto, turns on the
unified KV:

```text
common/arg.cpp:1399-1400        } else if (ex == LLAMA_EXAMPLE_SERVER) {
                                    params.n_parallel = -1;     // auto by default
tools/server/server.cpp:152-157 if (params.n_parallel < 0) {
                                    SRV_TRC("%s", "n_parallel is set to auto, using n_parallel = 4 and kv_unified = true\n");
                                    params.n_parallel = 4;
                                    params.kv_unified = true;
                                }
common/common.h:563             bool kv_unified        = false; // enable unified KV cache
common/arg.cpp:1713-1717        {"-kvu", "--kv-unified"}, {"-no-kvu", "--no-kv-unified"},
                                "use single unified KV buffer shared across all sequences (default: enabled if number of slots is auto)",
                                ... params.kv_unified = value;
common/common.cpp:1722          cparams.n_seq_max         = params.n_parallel;
common/common.cpp:1749          cparams.kv_unified        = params.kv_unified;
```

The split is made when the context is created:

```text
src/llama-context.cpp:288       cparams.n_ctx = GGML_PAD(cparams.n_ctx, 256);
src/llama-context.cpp:290-291   if (cparams.kv_unified) {
                                    cparams.n_ctx_seq = cparams.n_ctx;
src/llama-context.cpp:292-294   } else {
                                    cparams.n_ctx_seq = cparams.n_ctx / cparams.n_seq_max;
                                    cparams.n_ctx_seq = GGML_PAD(cparams.n_ctx_seq, 256);
src/llama-context.cpp:300-302       if (cparams.n_ctx != cparams.n_ctx_seq * cparams.n_seq_max) {
                                        cparams.n_ctx =  cparams.n_ctx_seq * cparams.n_seq_max;
                                        LLAMA_LOG_WARN("%s: n_ctx is not divisible by n_seq_max - rounding down to %u\n", ...
```

Each slot's limit is that per-sequence context, capped at the model's training
context:

```text
tools/server/server-context.cpp:1158-1161  int n_ctx_slot = llama_n_ctx_seq(ctx_tgt);
                                           if (n_ctx_slot > n_ctx_train) { ... n_ctx_slot = n_ctx_train; }
tools/server/server-context.cpp:1213       slot.n_ctx   = n_ctx_slot;
```

A slot that reaches its limit stops generating, because context shift is off by
default (`common/common.h:561`, `ctx_shift = false`). A prompt that does not fit
is refused:

```text
tools/server/server-context.cpp:1786-1788  if (!params_base.ctx_shift && slot.prompt.n_tokens() + 1 >= slot.n_ctx) {
                                               slot.truncated      = true;
                                               slot.stop           = STOP_TYPE_LIMIT;
tools/server/server-context.cpp:3091-3096  if (slot.task->n_tokens() >= slot.n_ctx) {
                                               send_error(slot, ..."request (%d tokens) exceeds the available context size (%d tokens), try increasing it", ...
                                               ERROR_TYPE_EXCEED_CONTEXT_SIZE);
```

The memory-fit pass does not move a `-c` that was given. With `-ngl` and `-ts`
also given, it aborts:

```text
common/fit.cpp:197      const bool     n_ctx_auto = cparams->n_ctx == 0;
common/fit.cpp:454      LOG_TRC("%s: context size set by user to %" PRIu32 " -> no change\n", __func__, cparams->n_ctx);
common/fit.cpp:462-463  if (mparams->n_gpu_layers != default_mparams.n_gpu_layers) {
                            throw common_params_fit_exception("n_gpu_layers already set by user to " ...
```

**With today's `-c 12288`** (from `kv_per_device.out.txt`, the formula above,
computed):

| launch | context per user | how |
|---|---|---|
| `-np 1` (today) | 12288 | one stream |
| `-np 2` | **6144** each | 2 streams of 6144 |
| `-np 4` | **3072** each | 4 streams of 3072 |
| `-np 2 -kvu` or `-np 4 -kvu` | up to 12288 each, from **one pool of 12288 cells that all slots share** | 1 stream |
| `-np 5` (not divisible) | 2560 each, and `n_ctx` becomes **12800**, not 12288 | the pad rounds up, despite the log's "rounding down" |

Under `-kvu`, a full pool fails every running request together. The server
halves the batch until it reaches 1, then errors and clears every slot that is
processing:

```text
tools/server/server-context.cpp:3576-3579  if (n_batch == 1 && ret == 1) {
                                               // TODO: try to terminate only the largest active slot/sequence and continue with the rest
                                               err = "Context size has been exceeded.";
tools/server/server-context.cpp:3596-3603  for (auto & slot : slots) {
                                               if (slot.is_processing()) {
                                                   send_error(slot, err);
                                                   slot.release();
                                                   ...
                                                   slot.prompt_clear();
```

**Closed** for this version: explicit `-np N` splits, `-kvu` shares, and both
limits follow from the lines above.

## Q2. `-np 1`: what happens to a second concurrent `/v1/chat/completions`?

**It is held, not refused.** The task goes to an in-memory deferred queue with no
size limit. It is started when the slot is released, in arrival order. The
engine has no wait timeout. The wait ends only when a slot frees or the client
disconnects.

When no slot is free, the task is deferred:

```text
tools/server/server-context.cpp:2282       server_slot * slot = get_available_slot(task);
tools/server/server-context.cpp:2288-2292  if (slot == nullptr) {
                                               // if no slot is available, we defer this task for processing later
                                               SRV_DBG("no slot is available, defer task, id_task = %d\n", id_task);
                                               queue_tasks.defer(std::move(task));
tools/server/server-context.cpp:2295-2298  if (slot->is_processing()) { ... queue_tasks.defer(std::move(task));
```

The deferred queue is an unbounded `std::deque`, and `defer` makes no size check:

```text
tools/server/server-queue.h:24-25    std::deque<server_task> queue_tasks;
                                     std::deque<server_task> queue_tasks_deferred;
tools/server/server-queue.cpp:76-79  void server_queue::defer(server_task && task) {
                                         std::unique_lock<std::mutex> lock(mutex_tasks);
                                         QUE_DBG("defer task, id = %d\n", task.id);
                                         queue_tasks_deferred.push_back(std::move(task));
```

Releasing a slot pops one deferred task. It takes the first task that asked for
that slot id, and otherwise the oldest task:

```text
tools/server/server-context.cpp:1220-1221  slot.callback_on_release = [this](int id_slot) {
                                               queue_tasks.pop_deferred_task(id_slot);
tools/server/server-queue.cpp:95-99        for (auto it = queue_tasks_deferred.begin(); ...) {
                                               if (it->id_slot == id_slot) { ... queue_tasks.emplace_front(std::move(*it));
tools/server/server-queue.cpp:105-108      if (!found) { ... queue_tasks.emplace_front(std::move(queue_tasks_deferred.front()));
                                               queue_tasks_deferred.pop_front();
```

While the task waits, the HTTP thread polls once a second. It gives up only when
the client has disconnected, and then it cancels the deferred task:

```text
tools/server/server-context.cpp:38         constexpr int HTTP_POLLING_SECONDS = 1;
tools/server/server-queue.cpp:552-556      server_task_result_ptr result = queue_results.recv_with_timeout(id_tasks, polling_interval_seconds);
                                           if (result == nullptr) {
                                               // timeout, check stop condition
                                               if (should_stop()) {
                                                   return nullptr;
tools/server/server-http.cpp:595           req.is_connection_closed           (the should_stop the handlers get)
tools/server/server-queue.cpp:602-617      server_response_reader::stop() ... server_task task(SERVER_TASK_TYPE_CANCEL); ...
tools/server/server-queue.cpp:376-378      queue_tasks_deferred.erase(std::remove_if(... rm_func), ...);
```

A streaming request sends nothing until its first result exists. The handler
blocks on the first result before it builds the stream, and the SSE keep-alive
ping covers only the gaps after that:

```text
tools/server/server-context.cpp:4256-4259  auto first_result = rd.next(req.should_stop);
                                           if (first_result == nullptr) {
                                               GGML_ASSERT(req.should_stop());
                                               return res; // connection is closed
tools/server/server-context.cpp:4337-4342  auto result = rd.next([... sse_ping_interval ...]() { ...
                                               } else if (sse_ping_interval > 0 && ggml_time_ms() - start_time > ...) {
                                                   timeout = true;
```

So a request held at `-np 1` sees silence on the wire for the whole wait, plus
its own prefill.

The limits that do exist do not refuse a second request:

```text
tools/server/server-http.cpp:310-312   if (n_threads_http < 1) {
                                           n_threads_http = std::max(params.n_parallel + 4, static_cast<int32_t>(std::thread::hardware_concurrency() - 1));
tools/server/server-http.cpp:319-320   const auto max_threads = static_cast<size_t>(n_threads_http + 1024);
                                       return new httplib::ThreadPool(n_threads_http, max_threads);
common/common.h:607-608                int32_t timeout_read        = 3600;          // http read timeout in seconds
                                       int32_t timeout_write       = timeout_read;  // http write timeout in seconds
tools/server/server-http.cpp:162-163   srv->set_read_timeout (params.timeout_read);
                                       srv->set_write_timeout(params.timeout_write);
```

The only "no slot available" error is on `GET /slots` with `?fail_on_no_slot`
(`server-context.cpp:4601`, `:4631-4635`). It is not on the completion path.

**Closed:** the second request is held, FIFO, with no queue limit and no engine
wait timeout. **Open:** whether cpp-httplib's 3600 s socket timeouts can end a
held request that writes nothing. The vendored `httplib.h` was not read.

## Q3. With `--rpc` and `-ts`, where does each slot's KV live, and does it multiply?

**Per layer, on the device that holds that layer, RPC workers included.** Every
slot's stream sits in the same per-layer tensor. The total is set by `-c`, not by
`-np`. At a fixed `-c`, adding slots divides the KV and adds none. To give every
slot the same context, `-c` must be `N × ctx_per_slot`. That multiplies the KV by
N on every device, the RPC worker included, in proportion to its layers.

Devices keep the order given in `-dev` (layer split mode):

```text
src/llama.cpp:180-181  for (ggml_backend_dev_t * dev = params.devices; *dev; ++dev) {
                           model->devices.push_back({false, *dev});
```

Layers are assigned by the cumulative `-ts` shares. The output layer is the last
index:

```text
src/llama-model.cpp:1436         std::copy(tensor_split, tensor_split + n_devices(), splits.begin());
src/llama-model.cpp:1449-1450    const int i_gpu_start = std::max(n_layer_all + 1 - n_gpu_layers, 0);
                                 const int act_gpu_layers = devices.empty() ? 0 : std::min(n_gpu_layers, n_layer_all + 1);
src/llama-model.cpp:1457-1458    const int layer_gpu = std::upper_bound(splits.begin(), splits.begin() + n_devices(), float(il - i_gpu_start)/act_gpu_layers) - splits.begin();
                                 auto * dev = devices.at(layer_gpu).dev;
src/llama-model.cpp:1469-1474    pimpl->dev_layer[il] = get_layer_buft_list(il); ... pimpl->dev_output = get_layer_buft_list(n_layer_all);
```

The KV is offloaded by default, so each layer's K and V go to that layer's device.
Each is one tensor of `[n_embd_gqa, kv_size, n_stream]`:

```text
common/common.h:568                 bool no_kv_offload     = false; // disable KV offloading
common/common.cpp:1745              cparams.offload_kqv       = !params.no_kv_offload;
src/llama-kv-cache.cpp:83           n_seq_max(n_seq_max), n_stream(unified ? 1 : n_seq_max), ...
src/llama-kv-cache.cpp:215-217      if (offload) {
                                        auto * dev = model.dev_layer(il);
                                        buft = ggml_backend_dev_buffer_type(dev);
src/llama-kv-cache.cpp:232-233      ggml_tensor * k = has_k ? ggml_new_tensor_3d(ctx, type_k, n_embd_k_gqa, kv_size, n_stream) : nullptr;
                                    ggml_tensor * v = has_v ? ggml_new_tensor_3d(ctx, type_v, n_embd_v_gqa, kv_size, n_stream) : nullptr;
src/llama-model.cpp:2577-2586       res = new llama_kv_cache(*this, hparams, params.type_k, params.type_v, !cparams.flash_attn,
                                        cparams.offload_kqv, cparams.kv_unified, cparams.n_ctx_seq, cparams.n_seq_max, ...
```

So the cells per layer are `n_ctx_seq × n_stream`: `C` when split (`C/N × N`) and
`C` when unified (`C × 1`), up to the 256-pad of Q1.

For today's launch, `kv_per_device.py` repeats those lines. The output is in
`kv_per_device.out.txt`:

```text
CUDA0: 27 layers (il 0..26)   CUDA1: 26 layers (il 27..52)   RPC0: 11 layers (il 53..63)   output layer: RPC0
```

That matches the hub's own plan for the run, `blocks 27` / `26` / `11`
(PR #42 `e2e/plan-3.txt:2-4`).

The KV in MiB below uses the product's `kv_bytes_per_token = 139264` from the rig
hello for this file (PR #42 `live/run3.jsonl:2`, 64 layers). It is an estimate,
and only the cell counts are read from source.

| launch | CUDA0 | CUDA1 | RPC0 |
|---|---|---|---|
| `-c 12288`, `-np` 1, 2, 3 or 4, with or without `-kvu` | 688.5 | 663.0 | 280.5 |
| `-c 24576 -np 2` (12288 per user) | 1377.0 | 1326.0 | 561.0 |
| `-c 49152 -np 4` (12288 per user) | 2754.0 | 2652.0 | 1122.0 |

**Closed** for placement and for the KV that scales with `n_ctx_seq × n_stream`.
**Open:** whether the compute buffers each device reserves grow with
`n_seq_max`. They are sized at reserve time, and that path was not read. Step 1
reads them from the engine's own startup lines.

## Q4. Does one decode step for several slots go over RPC as one batched graph?

**Reading, not a measurement.** Yes, when the busy slots fall in one ubatch.
The server puts every generating slot's next token into one `llama_batch`, with
the slot id as the sequence id, and calls `llama_decode` once per `n_batch`
chunk. `llama_decode` runs one graph per ubatch. The scheduler runs each
device's split of that graph once. For the RPC device, that means one
`GRAPH_COMPUTE` (or `GRAPH_RECOMPUTE`) message, its input copies, and the
read-back of its outputs. None of that loops per sequence.

The path is `update_slots` → `decode` → `llama_decode` → `llama_context::decode`
(ubatch loop) → `process_ubatch` → `graph_compute` →
`ggml_backend_sched_graph_compute_async` → `ggml_backend_sched_compute_splits` →
`ggml_backend_rpc_graph_compute`:

```text
tools/server/server-context.cpp:162         common_batch_add(batch, t.token, t.pos, { t.id_slot }, t.output);
tools/server/server-context.cpp:2868-2880   iterate(slots, [&](server_slot & slot) { if (slot.state != SLOT_STATE_GENERATING) return;
                                                ... else if (!slot_batched->can_batch_with(slot)) { return; }
                                                generating.push_back(&slot);
tools/server/server-context.cpp:2983-2985   iterate(generating, [&](server_slot & slot) { slot.handle_last_sampled_token(batch); });
tools/server/server-context.cpp:2754-2761   for (int32_t off = 0; off < batch.size(); off = off_next) { ...
                                                bool ok = decode(n_batch, off, batch_view);
tools/server/server-context.cpp:3565-3569   ret = llama_decode(ctx_tgt, batch_view);
                                            if (ret == 0 && has_output) { llama_synchronize(ctx_tgt); }
src/llama-context.cpp:1795-1816             do { const auto & ubatch = mctx->get_ubatch(); ... process_ubatch(ubatch, ...);
src/llama-context.cpp:1970                  } while (mctx->next());
src/llama-context.cpp:2494                  auto status = ggml_backend_sched_graph_compute_async(sched.get(), gf);
ggml/src/ggml-backend.cpp:1606-1609         for (int split_id = 0; split_id < sched->n_splits; split_id++) { ... split_backend = sched->backends[split_backend_id];
ggml/src/ggml-backend.cpp:1622-1634         for (int input_id = 0; input_id < split->n_inputs; input_id++) { ... ggml_backend_tensor_copy(input, input_cpy);
ggml/src/ggml-backend.cpp:1745              enum ggml_status ec = ggml_backend_graph_compute_async(split_backend, &split->graph);
ggml/src/ggml-rpc/ggml-rpc.cpp:1015-1025    bool reuse = cgraph->uid != 0 && rpc_dev_ctx->last_graph_uid == cgraph->uid;
                                            if (reuse) { ... send_async(RPC_CMD_GRAPH_RECOMPUTE, ...);
                                            } else { ... serialize_graph(...); send_async(RPC_CMD_GRAPH_COMPUTE, input_ptr, input_size);
ggml/src/ggml-rpc/ggml-rpc.cpp:956-958      static void ggml_backend_rpc_synchronize(ggml_backend_t backend) { ... rpc_ctx->dispatcher->synchronize();
```

Slots that may share a batch need the same task type, embedding size and LoRA
(`server-context.cpp:403-408`). Plain chat requests from different users all
qualify.

Three things in source make the count of exchanges per step larger than one:

1. **Gaps in slot ids split the ubatch (split KV only).** With `n_stream > 1`
   the KV uses `split_equal(..., sequential = true)`. That accepts only
   *consecutive* sequence ids into one ubatch:

   ```text
   src/llama-kv-cache.cpp:712   auto ubatch = n_stream == 1 ? balloc.split_simple(n_ubatch) : balloc.split_equal(n_ubatch, true, 0);
   src/llama-batch.cpp:537-540  // accept only increasing sequence ids
                                if (sequential) {
                                    add = add && (cur_seq_set.empty() || batch.seq_id[i][0] == last_seq_id + 1);
   ```

   Busy slots 0 and 2, with slot 1 idle, take two ubatches, so two graphs and two
   RPC exchanges per step. `-kvu` (`n_stream == 1`) uses `split_simple`, which
   has no such rule.
2. **A prefill beside decodes adds ubatches (split KV only).** `split_equal`
   takes the same token count from every sequence in a ubatch, and stops
   growing when any sequence runs out (`src/llama-batch.cpp:573-603`). A
   one-token decode therefore caps that ubatch at one token per sequence, and
   the prefill continues in further ubatches.
3. **A change of batch shape resends the whole graph.** A graph is reused only
   when its parameters match (`src/llama-context.cpp:1339`). Otherwise it is
   rebuilt (`:1350-1358`), gets a new uid, and goes out as a full
   `serialize_graph` `GRAPH_COMPUTE` instead of the small `GRAPH_RECOMPUTE`
   (`ggml-rpc.cpp:1015-1025`). The number of busy slots changes that shape.

**The bytes per step do grow with N.** In this launch the output layer sits on
RPC0 (Q3). Sampling is not offloaded to the backend by default, so raw logits
are needed. Each decode step therefore reads back `n_outputs × n_vocab × 4`
bytes of logits from RPC0, one output per busy slot:

```text
common/common.h:295          bool backend_sampling = false;      (in struct common_params_sampling, :223)
src/llama-context.cpp:1627-1628  if (samplers.find(seq_id) == samplers.end()) { return true; }   (needs_raw_logits)
src/llama-context.cpp:1863   if (logits.data && t_logits && n_outputs > 0 && needs_raw_logits(ubatch, sampling.samplers)) {
src/llama-context.cpp:1864   ggml_backend_t backend_res = ggml_backend_sched_get_tensor_backend(sched.get(), t_logits);
src/llama-context.cpp:1873   ggml_backend_tensor_get_async(backend_res, t_logits, logits_out, 0, n_outputs*n_vocab*sizeof(float));
ggml/src/ggml-rpc/ggml-rpc.cpp:947-953  ggml_backend_rpc_get_tensor_async(...) ... send_async(RPC_CMD_GET_TENSOR, ...);
```

`n_vocab` was not read from the GGUF here.

**Closed (as a reading):** one batched graph per ubatch, and per-split RPC
traffic with no per-slot loop. **Open, and for step 1 to measure:** whether that
hides the per-token round trip in wall-clock terms. That depends on how much of
a step is round-trip latency rather than compute and bytes, which source cannot
say. Also open: what slot ids the server hands concurrent requests in practice,
which decides whether gap 1 occurs. LRU selection is in
`server-context.cpp:1519-1540`, and how often it leaves gaps under real traffic
was not traced.

## Q5. Prompt cache and prefix reuse between slots (brief)

Relevant, and on by default. `--cache-reuse` is off. The host-RAM prompt cache
is on with an 8192 MiB budget, and idle slots are saved to it whenever a task
starts. Slot save/restore to disk is off without `--slot-save-path`.

```text
common/common.h:611-616  int32_t n_cache_reuse = 0; ... bool cache_prompt = true; bool cache_idle_slots = true; ... int32_t cache_ram_mib = 8192;
common/common.h:678      float slot_prompt_similarity = 0.1f;
tools/server/server-context.cpp:1277       prompt_cache = std::make_unique<server_prompt_cache>(params_base.cache_ram_mib, n_ctx);
tools/server/server-context.cpp:2320-2325  if (params_base.cache_idle_slots) { for (auto & slot : slots) { if (!slot.is_processing()) { ... slot.prompt_save(*prompt_cache)
tools/server/server-context.cpp:1549-1556  if (update_cache) { ... ret->prompt_save(*prompt_cache); if (!ret->prompt_load(*prompt_cache, task.tokens)) { ret->prompt_clear();
```

Saving a slot copies its KV from every device to host memory. The KV of RPC-held
layers is fetched with a synchronous `GET_TENSOR`, one request per tensor:

```text
tools/server/server-context.cpp:271     llama_state_seq_get_data_ext(ctx_tgt, cur->data.main.data(), cur_size_tgt, id, LLAMA_STATE_SEQ_FLAGS_NONE);
src/llama-context.cpp:2986-2987         } else { io = std::make_unique<llama_io_write_host>(dst, size); }
src/llama-context.cpp:2568-2569         for (const auto & winfo : winfos) { ggml_backend_tensor_get(winfo.tensor, winfo.ptr, winfo.offset, winfo.size);
ggml/src/ggml-rpc/ggml-rpc.cpp:719-725  ggml_backend_rpc_buffer_get_tensor(...) ... ctx->dispatcher->send(RPC_CMD_GET_TENSOR, request, sizeof(*request), data, size);
```

**Closed** that this traffic exists. **Open:** its size in time per slot switch.
Also open: how the default 8192 MiB cache budget sits against the head
container's memory cap. That cap is also 8192 MiB by default
(`src/mcgyvr/rig/sharing.py:52`, `:107`) and covers the whole process.

---

## What this means for step 1 and step 2

**The planner's count.** The KV on a device is
`layers on that device × KV bytes per layer per token × n_ctx`. Here `n_ctx` is
the total, `N × ctx_per_slot`, padded as in Q1. `-np` alone changes nothing in
that sum, and `-c` changes everything. So `HeadStartBody` must say which number
the hub means. If `ctx` stays the total, each user gets `ctx/N`: 6144 at N = 2
and 3072 at N = 4 with today's 12288. If `ctx` means per user, the fit must
count `N × ctx` on every device, and the RPC worker's share rises with it
(280.5 → 1122 MiB at N = 4 with this split, using the hello's estimate).
`-kvu` keeps the sum at `ctx` but makes it a shared pool. When that pool fills,
every running request fails (Q1). The KV is not the only thing the fit must
count: compute buffers versus N are open (Q3).

**Cells step 1 must include** (one-variable ladder, one cell per driver
invocation, prompt and output counts matched, as `okf/must-read/reading-results.md`
requires):

- `-np` 1, 2, 4 at a fixed `-c 12288`, and at `-c N × 12288`, with all N slots
  busy. Read the engine's own startup lines (`n_ctx_seq`, `kv_unified`,
  `KV buffer size` per device) to confirm the Q1 and Q3 readings on the run.
- The same ladder with the RPC worker in the split, and a control with no RPC
  device (the same model at a size that fits locally, or the same split with the
  RPC layers moved local). The difference between the two isolates the RPC
  round trip that batching is predicted to hide.
- A cell with busy slots on non-consecutive ids (requests can name `id_slot`),
  against the same cell on consecutive ids. This prices the ubatch split of Q4
  (1).
- A decode-only cell against a cell where one slot prefills while the others
  decode. This prices Q4 (2), and is the realistic workload anyway.
- `-kvu` as its own arm, never mixed into the split-KV numbers.
- `--cache-ram 0` against the default, at N > 1 with turnover. This prices the
  slot-save read-back over RPC (Q5).
- At `-np 1`: two concurrent requests. Confirm the second is held (no 5xx),
  starts in FIFO order, and receives no bytes before its first token (Q2).

**For step 2 (the hub's queue).** The engine already queues without bound or
timeout (Q2). The hub's bounded wait is therefore the only bound there is. The
engine serves its own deferred queue oldest first, so the hub's fair order
survives only if the hub sends the head no more requests than it has slots.
That means the relay cap must equal the slot count, as #46 already plans,
rather than 4 over `-np 1`. A held request is silent on the wire until its first
token. Relay and client idle timeouts must allow for that, or the hub must hold
the request itself.

## Files

- `version-id.txt`: the commands and outputs that pinned the engine version.
- `kv_per_device.py`: the desk calculation for Q1 and Q3. It re-implements the
  quoted lines and makes no measurement.
- `kv_per_device.out.txt`: its output, as run on 2026-10-02.
