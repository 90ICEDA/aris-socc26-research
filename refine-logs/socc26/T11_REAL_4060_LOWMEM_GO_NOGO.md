# T11 GO / NO-GO Smoke Note

## Summary

- overlap_0 median TTFT: 41.124 ms
- overlap_100 median TTFT: 31.105 ms
- median delta overlap_0 - overlap_100: 10.019 ms
- p95 delta overlap_0 - overlap_100: 2.848 ms
- decision: NO-GO for this setup: separation is weak; try longer prefixes, more samples, or quieter GPU

## Raw condition stats

| condition | n | median TTFT ms | p95 TTFT ms | mean TTFT ms |
|---|---:|---:|---:|---:|
| overlap_0 | 10 | 41.124 | 54.061 | 40.490 |
| overlap_100 | 10 | 31.105 | 51.213 | 35.017 |

## Notes

- This is smoke evidence only, not a final claim.
- Results are synthetic and manifest-backed.
- If separation is weak, increase context length and sample count before abandoning the track.