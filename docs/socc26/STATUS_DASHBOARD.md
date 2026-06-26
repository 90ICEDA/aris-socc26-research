# SoCC26 Three-Track Status Dashboard

## Current checkpoint

Tag: socc26-three-track-offline-v0

## Track status

| Track | Topic | Current artifact | Status | Next step |
|---|---|---|---|---|
| T11 | Prefix/KV cache isolation | dry-run pipeline + low-memory vLLM probe | waiting for free GPU | run real vLLM smoke when VRAM is available |
| T12 | Continuous batching fairness / SLO robustness | offline batching simulator + three plots | offline smoke done | inspect trends, then port workload to real vLLM/SGLang |
| T13 | Replay-gated CloudOps agent | offline contract checker + gate table | offline smoke done | add minikube/k3s replay |

## Submission framing

- T11: privacy / cache isolation / leakage-performance frontier
- T12: availability / fairness / strategic tenant robustness
- T13: autonomous cloud safety / replay + contracts

## Rules

- No fabricated results.
- Dry-run and offline simulation are not real serving results.
- Real T11/T12 claims require vLLM/SGLang measurement.
- GPU-contested runs must be marked as noisy smoke only.
