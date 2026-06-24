# SoCC 2026 ARIS Track Plan

This branch scaffolds three SoCC 2026 research tracks under the ARIS research workflow.

## Tracks

- T11_llm_cache_isolation: cache isolation, prefix/KV-cache side-channel measurement, and tenant-aware cache policy benchmark.
- T12_llm_batch_fairness: continuous batching fairness, adversarial tenant workloads, and SLO robustness.
- T13_cloudops_replay_guard: replay-gated cloud operations agent with contract checking.

## Shared principles

- No fabricated results.
- Every experiment must have a manifest.
- Every result must include git commit, device, engine, model, workload, command, and timestamp.
- A100/H100-class GPUs are optional for final generality checks only, not for smoke tests.
- T11 and T12 share the LLM serving harness.
- T13 uses a separate CloudOps replay/contract harness.

## Immediate goal

Produce one smoke artifact per track:

- T11: TTFT difference between 0% and 100% prefix overlap.
- T12: victim SLO degradation under adversarial tenant workload.
- T13: contract gate table for 5 cloud incident scenarios.
