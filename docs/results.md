# Results

Every quality score below comes from a private 11-category eval bank whose questions are not published; those scores are reported, not reproducible by readers. The engine-level measurements that readers can reproduce with the published flags and `scripts/needle_probe.py` are a single-depth needle probe and the cold/hit prefill timing; the 27-sample matrix (three depths × nine needles, private corpus) and the K1 throughput numbers are reported only. Category names (c1-kbqa … c10-sre-ops) are disclosed; prompts, gold answers, and per-item scoring detail are not. Each table carries a one-line note of the measurement conditions above it. Full prose context is in [`../README.md`](../README.md).

## 1. 1M context validation (non-thinking mode)

Conditions: community cluster recipe `qwen3.8-flash-next-nvfp4-cluster` in [github.com/eugr/spark-vllm-docker](https://github.com/eugr/spark-vllm-docker) (image `vllm-node-b12x`, digest prefix `d6fb7a6a277d`, vLLM build `v0.1.dev20759+gb40673cd0`), TP2 over RoCE (200GbE QSFP direct link), fp8 KV, MTP4, `--gpu-memory-utilization 0.70`, YaRN factor 4, `--max-model-len 1000000`. Weights: [local-inference-lab/Qwen3.8-Flash-Next-NVFP4](https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4) on Hugging Face (revision not recorded). Host driver and kernel: not recorded in this table.

| Metric | Value | Condition |
|---|---|---|
| KV pool tokens | 3,441,324–3,482,606 | engine reports ~3.44× one 1M-token request; a 1M request occupies ~29% of the pool; range across starts |
| c1-kbqa short-text | 96.7 / 96.7 | two runs; no regression vs 262K reference run |
| c4-code short-text | 95.8 / 95.8 | two runs; no regression vs 262K reference run |
| c2-longctx (30 items incl. 200K) | 100 / 96.7 | two runs; exceeds 262K reference run |
| 262K reference run (dual-node native 262K, same bank, different day) | c1 95.0, c4 91.7, c2 98.3 | two-run medians; a different run on a different day, shown for comparison next to the 1M numbers |
| XL needle 27-sample, strict | 21/27 = 77.8% | xl r1/r2/xl2 each 7/9; strict scoring |
| XL needle content recall, 400K | 9/9 | content-level recall (not strict) |
| XL needle content recall, 700K | 9/9 | content-level recall (not strict) |
| XL needle content recall, 950K | 9/9 | content-level recall (not strict) |
| Cold prefill 400K (corpus) | ≈3 min | single run |
| Cold prefill 700K (corpus) | ≈6.3 min | single run |
| Cold prefill 950K (corpus) | ≈10 min | single run |
| End-to-end wall, 950K random-word prompt, 24-token answer (cold, no prefix hit) | 857 s ≈ 1.1K tok/s | single run; reported wall is end-to-end for a 24-token answer (cold prefill dominates) |
| 950K cold ×3 | 856 / 860 / 859 s, all correct | cold = no prefix-cache hit because the intervening requests evicted the pool; hit = the same prompt re-sent immediately (7.9 s); zero crashes |
| 200K temp 0 ×3 | text identical across three cold runs | all correct, hit=cold |
| 3-way 900K concurrent | 793 / 1583 / 2373 s, all correct | three prompts with distinct prefixes sent at once; the engine queued them within capacity, so completions are serial and the client timeout must exceed the last one (2373 s); zero crashes |
| K1 decode | 52.0–52.9 tok/s | single-stream decode on a 400-token prose completion; parity with 262K baseline within this workload and observation precision (no paired native repeat count recorded; not a general zero-speed-cost claim) |
| K1 prefill | 3034 tok/s | cold prefill on a ~2.3K-token prompt; parity with 262K baseline |
| K1 6-stream | 88–89 tok/s | six concurrent streams aggregate; parity with 262K baseline |
| Health (both nodes) | NVRM/Xid 0; zero engine errors; no restarts | author-reported (private switch script); observation interval and restart/counter collection method not defined here |

## 2. Native 262K vs 1M YaRN factor 4 (single model)

Conditions: thinking on, `--tool-call-parser qwen3_coder`, `--reasoning-parser qwen3`; base column = 1M YaRN factor 4 with `--max-model-len 1000000` and the YaRN `text_config.rope_parameters` override, native column = the same model at its native 262K context (no YaRN override, `--max-model-len 262144`); both columns with MTP4, `--no-async-scheduling`, and the same two-run median statistic. Exact thinking sampling values (temperature/top_p/top_k) and repeat count are not recorded in this table; scores are absolute category scores from the private eval bank, wall clock is a ratio of native to base.

| Category | Base (1M YaRN×4) | Native 262K |
|---|---|---|
| c1-kbqa | 88.3 | 93.3 (+5.0) wall 0.98× |
| c5-extract | 84.2 | 86.0 (+1.8) wall 1.31× |
| c7-agentic-if | 91.7 | 92.5 (+0.8) wall 1.02× |
| c8-judgment | 98.3 | 98.3 (+0.0) wall 1.05× |
| c9-long-coding | 100.0 | 100.0 (+0.0) wall 0.62× |

Reading: native 262K matches or beats the 1M YaRN tier on the five categories we measured and is faster on c9-long-coding (native took 0.62× the wall clock of the 1M YaRN run, i.e. YaRN took ~1.6× native). The 1M tier's value is the window itself, not a short-text advantage — hence native 262K is the recommended default production tier with 1M YaRN available on demand (switch time ≈4 minutes, author-reported via the private switch script).
