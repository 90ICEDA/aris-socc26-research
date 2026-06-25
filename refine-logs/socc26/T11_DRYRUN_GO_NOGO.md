# T11 GO / NO-GO Smoke Note

## Summary

- overlap_0 median TTFT: 616.272 ms
- overlap_100 median TTFT: 360.952 ms
- median delta overlap_0 - overlap_100: 255.320 ms
- p95 delta overlap_0 - overlap_100: 287.278 ms
- decision: GO: measurable TTFT separation exists in smoke run

## Raw condition stats

| condition | n | median TTFT ms | p95 TTFT ms | mean TTFT ms |
|---|---:|---:|---:|---:|
| overlap_0 | 30 | 616.272 | 673.906 | 620.516 |
| overlap_100 | 30 | 360.952 | 386.628 | 358.500 |

## Notes

- This is smoke evidence only, not a final claim.
- Results are synthetic and manifest-backed.
- If separation is weak, increase context length and sample count before abandoning the track.