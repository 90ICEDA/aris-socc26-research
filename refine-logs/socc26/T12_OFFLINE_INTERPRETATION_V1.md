# T12 Offline Smoke Interpretation v1

This note interprets the offline simulator output. It is not a real vLLM/SGLang measurement.

## Main conclusion

- `long_decode` is the strongest current signal: baseline FCFS shows rapidly increasing victim TTFT SLO violation as adversarial load increases.
- `token_budget_guard` reduces but does not eliminate long-decode interference.
- `long_prompt` currently shows zero SLO violation under the current parameters, so it should be treated as a weak or negative signal, not the main story.

## Highest-load rows

| attack | policy | adv_load | victim p95 TTFT ms | victim mean TTFT ms | victim max TTFT ms | SLO violation |
|---|---|---:|---:|---:|---:|---:|
| burst | baseline_fcfs | 2.00 | 25623.74 | 14501.62 | 27330.04 | 0.984 |
| burst | token_budget_guard | 2.00 | 601.11 | 190.79 | 836.19 | 0.019 |
| burst | victim_priority_guard | 2.00 | 845.90 | 289.35 | 1185.65 | 0.051 |
| long_decode | baseline_fcfs | 2.00 | 127580.59 | 67481.70 | 133327.06 | 0.965 |
| long_decode | token_budget_guard | 2.00 | 2189.46 | 849.92 | 2892.29 | 0.450 |
| long_decode | victim_priority_guard | 2.00 | 2189.46 | 849.92 | 2892.29 | 0.450 |
| long_prompt | baseline_fcfs | 2.00 | 289.58 | 62.99 | 561.34 | 0.000 |
| long_prompt | token_budget_guard | 2.00 | 18.63 | 14.08 | 41.55 | 0.000 |
| long_prompt | victim_priority_guard | 2.00 | 171.84 | 42.36 | 314.96 | 0.000 |

## Paper pivot

T12 should focus on decode-slot occupancy rather than generic long-request abuse.

Proposed framing:

> Existing continuous batching improves throughput, but strategic long-decode tenants can monopolize active decode slots and break latency SLOs for short interactive tenants.

## Next real-system experiment

1. Port only the long-decode workload to real vLLM/SGLang first.
2. Measure victim TTFT, TBT/TPOT, P95/P99, and SLO violation.
3. Compare baseline FCFS against per-tenant max active sequences, output-token budget, and admission shaping.