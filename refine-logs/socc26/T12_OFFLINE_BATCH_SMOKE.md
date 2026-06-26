# T12 Offline Batching-Fairness Smoke

This is an offline simulator, not a real vLLM experiment.

## Goal

Measure whether adversarial tenant workloads can increase victim TTFT SLO violation, and whether simple tenant-aware guards reduce the effect.

## Best smoke rows

| attack | adv_load | policy | victim_n | p95 TTFT ms | SLO violation rate |
|---|---:|---|---:|---:|---:|
| burst | 2.00 | baseline_fcfs | 124 | 25623.74 | 0.984 |
| burst | 2.00 | token_budget_guard | 124 | 601.11 | 0.019 |
| burst | 2.00 | victim_priority_guard | 124 | 845.90 | 0.051 |
| long_decode | 2.00 | baseline_fcfs | 124 | 127580.59 | 0.965 |
| long_decode | 2.00 | token_budget_guard | 124 | 2189.46 | 0.450 |
| long_decode | 2.00 | victim_priority_guard | 124 | 2189.46 | 0.450 |
| long_prompt | 2.00 | baseline_fcfs | 124 | 289.58 | 0.000 |
| long_prompt | 2.00 | token_budget_guard | 124 | 18.63 | 0.000 |
| long_prompt | 2.00 | victim_priority_guard | 124 | 171.84 | 0.000 |

## Interpretation

- `baseline_fcfs` is the no-protection baseline.
- `victim_priority_guard` represents a simple latency-sensitive tenant preference.
- `token_budget_guard` represents a simple per-epoch adversarial prefill-token budget.
- This result is only a smoke signal. It must later be validated against vLLM/SGLang real serving traces.

## Next step

Reuse the T11 OpenAI-compatible serving harness to replace simulated TTFT with real TTFT under mixed-tenant workloads.