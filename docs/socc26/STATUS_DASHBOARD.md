# SoCC26 Three-Track Status Dashboard

## Current checkpoint

Tag: socc26-three-track-offline-v0

## Track status

| Track | Topic | Current artifact | Status | Next step |
|---|---|---|---|---|
| T11 | Prefix/KV cache isolation | dry-run pipeline + low-memory vLLM probe | waiting for free GPU | run real vLLM smoke when VRAM is available |
| T12 | Continuous batching fairness / SLO robustness | offline batching simulator + three plots | offline smoke done | inspect trends, then port workload to real vLLM/SGLang |
| T13 | Replay-gated CloudOps agent | offline checker + real kind/kubectl replay smoke | k8s replay smoke done | add unsafe-action ablation and recovery-time metric |

## Submission framing

- T11: privacy / cache isolation / leakage-performance frontier
- T12: availability / fairness / strategic tenant robustness
- T13: autonomous cloud safety / replay + contracts

## Rules

- No fabricated results.
- Dry-run and offline simulation are not real serving results.
- Real T11/T12 claims require vLLM/SGLang measurement.
- GPU-contested runs must be marked as noisy smoke only.

## T11 Real vLLM Checkpoint - RTX 4060 Low-Memory Smoke

Status: DONE.

Evidence:
- Real vLLM server successfully launched on RTX 4060 Laptop GPU.
- Model: Qwen/Qwen2.5-0.5B-Instruct.
- vLLM version: 0.6.6.post1.
- Prefix caching enabled.
- Workload: t11_prefix_smoke_4060_lowmem.jsonl.
- Result: overlap_100 has lower mean TTFT than overlap_0.
- overlap_0 mean TTFT: 40.49 ms.
- overlap_100 mean TTFT: 35.02 ms.
- Observed GPU prefix cache hit rate: 78.39%.
- Output note: refine-logs/socc26/T11_REAL_4060_LOWMEM_GO_NOGO.md.

Interpretation:
This confirms that the T11 pipeline has moved from dry-run to real vLLM evidence. The result is still a low-memory smoke test, not the final evaluation, but it validates the measurement harness and prefix-cache effect.

Next:
Run a larger controlled T11 experiment with more repetitions, more overlap levels, and randomized request order.
