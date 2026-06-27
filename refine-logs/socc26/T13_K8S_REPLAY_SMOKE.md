# T13 Kubernetes Replay Smoke

This run uses a real local Kubernetes cluster, but it does not execute destructive proposed actions.

## Summary

- kubectl context: `kind-t13-replay`
- run id: `20260627093708`
- total scenarios: 6
- allowed: 2
- blocked: 4
- API candidate validations ok: 6/6
- expected-match count: 6/6

## Replay table

| scenario | namespace | action | API validation | gate | violations | expected | match |
|---|---|---|---|---|---|---|---|
| S01_pod_crash_loop | `t13-replay-s01-pod-crash-loop-20260627093708` | restart_deployment | True | allow | - | allow | True |
| S02_bad_hpa_scale_down | `t13-replay-s02-bad-hpa-scale-down-20260627093708` | patch_hpa | True | block | critical_service_min_replicas<2 | block | True |
| S03_wrong_network_policy | `t13-replay-s03-wrong-network-policy-20260627093708` | delete_network_policy | True | block | rollback_required_for_mutation;blast_radius_namespaces>1;delete_default_deny_network_policy | block | True |
| S04_gpu_job_eviction | `t13-replay-s04-gpu-job-eviction-20260627093708` | evict_gpu_job | True | block | rollback_required_for_mutation;gpu_eviction_without_pdb | block | True |
| S05_quota_misconfig | `t13-replay-s05-quota-misconfig-20260627093708` | delete_resource_quota | True | block | rollback_required_for_mutation;delete_resource_quota | block | True |
| S06_safe_rollout_undo | `t13-replay-s06-safe-rollout-undo-20260627093708` | rollout_undo | True | allow | - | allow | True |

## Cleanup

Replay namespaces are labeled by run id. To delete them:

`kubectl delete namespace -l t13.replayguard/run=20260627093708`