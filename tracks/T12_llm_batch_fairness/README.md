# T12: LLM Batch Fairness

## Research question

Can strategic or adversarial tenants exploit continuous batching in multi-tenant LLM serving to degrade victim TTFT/TBT/SLO, and can admission shaping or token-time budgeting improve robustness?

## Scope

This track focuses on availability, fairness, batching abuse, per-tenant SLO, and adversarial workload generation.

## First smoke target

Run a two-tenant workload:

- victim: short prompt, short output, strict TTFT SLO
- adversary: long prompt, long decode, or burst arrival

Measure victim latency and SLO violation rate.

## Required outputs

- `workloads/benign_short.jsonl`
- `workloads/adversarial_long_prompt.jsonl`
- `workloads/adversarial_burst.jsonl`
- `results/smoke/t12_victim_slo_under_burst.csv`
- `figures/t12_slo_violation_vs_adv_load.png`
