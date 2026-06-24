# T13: CloudOps Replay Guard

## Research question

Can LLM-generated cloud operation actions be safely gated by replay sandboxing, contract checking, blast-radius estimation, and rollback verification before execution?

## Scope

This track focuses on autonomous cloud operations, Kubernetes/minikube scenarios, contract checking, unsafe action blocking, and replay-gated execution.

## First smoke target

Create 5 synthetic cloud incident scenarios and evaluate whether a contract gate allows or blocks the proposed action.

## Required outputs

- `scenarios/pod_crash_loop.yaml`
- `scenarios/bad_hpa_scale_down.yaml`
- `scenarios/wrong_network_policy.yaml`
- `contracts/slo_availability.yaml`
- `contracts/no_cross_namespace_access.yaml`
- `results/smoke/t13_contract_gate_table.csv`
