# T11: LLM Cache Isolation

## Research question

Does prefix/KV-cache reuse in multi-tenant LLM serving create measurable privacy/performance tradeoffs, and can tenant-aware cache policies reduce leakage while preserving serving efficiency?

## Scope

This track focuses on cache isolation, prefix overlap workloads, TTFT/TBT measurements, and tenant-aware cache policies.

## First smoke target

Run a small vLLM/SGLang-compatible workload with two cases:

- 0% prefix overlap
- 100% prefix overlap

Measure TTFT distribution and record results in `results/smoke/`.

## Required outputs

- `workloads/prefix_templates.json`
- `scripts/gen_prefix_workload.py`
- `scripts/run_vllm_smoke.py`
- `scripts/analyze_ttft.py`
- `results/smoke/t11_smoke_latency.jsonl`
- `figures/t11_ttft_smoke.png`
