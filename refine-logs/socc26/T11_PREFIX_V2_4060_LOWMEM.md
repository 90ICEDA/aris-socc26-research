# T11 Real vLLM Prefix-Overlap V2

Status: completed controlled low-memory RTX 4060 vLLM experiment.

## Data quality

- total raw rows: 153
- skipped rows with request error: 3
- skipped rows with missing TTFT: 0
- skipped TTFT outliers above 5000 ms: 1

## Summary

| condition | used n | raw n | mean TTFT ms | median TTFT ms | p95 TTFT ms | skipped error | skipped outlier |
|---|---:|---:|---:|---:|---:|---:|---:|
| overlap_0 | 29 | 30 | 54.87 | 56.66 | 65.97 | 1 | 0 |
| overlap_25 | 29 | 30 | 54.37 | 51.32 | 89.32 | 1 | 0 |
| overlap_50 | 29 | 30 | 52.09 | 52.09 | 67.67 | 0 | 1 |
| overlap_75 | 29 | 30 | 47.36 | 48.27 | 76.14 | 1 | 0 |
| overlap_100 | 30 | 30 | 46.61 | 46.72 | 62.72 | 0 | 0 |

## Key comparison

- overlap_0 mean TTFT: 54.87 ms
- overlap_100 mean TTFT: 46.61 ms
- delta: -8.26 ms (-15.06%)
- Interpretation: higher prefix overlap reduces TTFT in this low-memory smoke setting.

## Caveat

This is a low-memory RTX 4060 smoke experiment. Timeout/error rows and large timeout-induced TTFT outliers are explicitly excluded from the clean summary and reported above.
