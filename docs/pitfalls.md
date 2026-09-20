# Pitfalls

Each pitfall below is laid out as **symptom → root cause → fix → how we found it**. The numbers come from the runs described in [`results.md`](results.md) and [`../README.md`](../README.md). The async-scheduling × MTP runaway loop and its single-variable isolation table are documented in a separate cookbook, [`dell-pro-max-gb10-vllm-mtp-async-runaway`](https://github.com/ryangu00/dell-pro-max-gb10-vllm-mtp-async-runaway).

---

## 1. `QSA sequence length 1000000 exceeds the configured limit 262144` on any request >262K

**Symptom.** The engine starts cleanly, but once the engine is configured with `--max-model-len 1000000`, any request whose prompt-plus-generated sequence length exceeds the draft's inherited 262144 limit crashes with:

```
QSA sequence length 1000000 exceeds the configured limit 262144
```

with a stack trace in `mtp.py`. We found no report of this in the vLLM issue tracker as of 2026-09-19.

**Root cause.** This version of vLLM constructs the draft `ModelConfig` with `max_model_len=speculative_config.max_model_len`. When `--hf-overrides` is a plain dict, it does not propagate to the draft; `max_model_len` then defaults to `None`, so the draft inherits the model's original 262144 rope limit. The main model is happy at 1M, but the MTP draft path is silently still capped at 262144.

**Fix.** Pass `"max_model_len": 1000000` explicitly *inside* the `--speculative-config` JSON dict:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":4,"max_model_len":1000000}'
```

**How we found it.** The crash message names the limit (`262144`) verbatim, which is the model's native rope ceiling — that pointed straight at the draft config rather than the main model. The `mtp.py` stack trace in the crash log confirmed the failure was on the draft `ModelConfig` path, not the serving path.

---

## 2. Runaway loops on agent tasks (async scheduling × MTP)

This pitfall — c3-tool 122 s and c7-agentic-if 214 s with async on, versus 46 s and 52 s after `--no-async-scheduling` (2.6× and 4.1×); the DeepSeek baseline on the same day was 39 s and 42 s, with 3/120 runaway responses; the accepted-token bookkeeping between the host and device is the suspected mechanism (community issues #53912 and #51571 describe the same pattern); what we measured is the correlation: 3/120 with async on, 0/120 with it off — and the single-variable isolation table (120 questions/tier) are documented in [`dell-pro-max-gb10-vllm-mtp-async-runaway`](https://github.com/ryangu00/dell-pro-max-gb10-vllm-mtp-async-runaway). The fix is the single flag `--no-async-scheduling` already listed in the recipe table.

---

## 3. Short-text category (c1) drops 5 points after YaRN factor 4

**Symptom.** In the native-vs-1M comparison, c1-kbqa drops from 93.3 (native 262K) to 88.3 (1M YaRN×4), a −5.0 regression. c9-long-coding is ~1.6× wall clock under YaRN (native took 0.62× of the 1M YaRN run).

**Root cause.** Static YaRN hurts short text, as the official model card warns (card revision not recorded; this is an observed configuration effect, not a mechanism we proved here). Confirmed on our eval bank: c1 −5.0, c9 ~1.6× wall clock.

**Fix.** Use native 262K for short-text workloads; reserve YaRN 1M for runs that actually need the context. The recommended deployment is native 262K as the default production tier with 1M YaRN available on demand (switch time ≈4 minutes, author-reported via the private switch script; start/stop boundary not defined here).

**How we found it.** The native-vs-1M comparison was designed exactly to surface this trade-off. Native 262K beat the 1M base on c1 (+5.0) and c5 (+1.8) while matching c8/c9, so the YaRN tier buys a window, not a short-text advantage.

---

## 4. Container logs disappear when the container is removed

**Symptom.** After stopping the serving container with `docker rm -f <container>`, the vLLM engine logs for that run are gone — including the evidence needed to diagnose an engine death mid-run.

**Root cause.** The vLLM log lives *inside* the container; `rm -f` removes the container and its filesystem with it.

**Fix.** Add a `dump` step to the switch script's stop routine that copies the in-container log out to the host *before* the container is removed, and only remove the container after the dump succeeds:

```
docker logs --tail 4000 <container> > <LOG_DIR>/lastlog-<container>.log 2>&1
docker rm -f <container>
```

`--tail 4000` truncates to the last 4000 lines, so keep the previous dump as `<LOG_DIR>/lastlog-<container>.log.prev` before overwriting. `2>&1` captures the non-TTY container's stderr alongside stdout; `docker logs` only mirrors the container's stdout/stderr stream, so for any other in-container log file, export it separately (e.g. `docker cp <container>:/path/to/file <LOG_DIR>/`).

---

## 5. Our results-comparison script fails on the c2 subset after merging run directories

**Symptom.** After merging several run directories into one, the eval bank's comparison step fails on the c2 subset.

**Root cause.** The merged directory omitted the `raw/` subdirectory that the comparison step expects.

**Fix.** Include `raw/` when merging results directories.

**How we found it.** The failure was scoped to one category (c2) and one operation (the merge), and the comparison error pointed at a missing path under c2 — a directory diff against a known-good single-run directory showed `raw/` as the only missing entry.
