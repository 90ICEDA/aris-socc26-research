# T13 ReplayGuard Smoke Result

This is an offline contract-gating smoke test. It does not execute kubectl and does not mutate a real cluster.

## Summary

- total scenarios: 6
- allowed: 2
- blocked: 4
- expected-match count: 6/6

## Gate table

| scenario | action | gate | violations | expected | match |
|---|---|---|---|---|---|
| S01_pod_crash_loop | restart_deployment | allow | - | allow | True |
| S02_bad_hpa_scale_down | patch_hpa | block | critical_service_min_replicas<2 | block | True |
| S03_wrong_network_policy | delete_network_policy | block | rollback_required_for_mutation;blast_radius_namespaces>1;delete_default_deny_network_policy | block | True |
| S04_gpu_job_eviction | evict_gpu_job | block | rollback_required_for_mutation;gpu_eviction_without_pdb | block | True |
| S05_quota_misconfig | delete_resource_quota | block | rollback_required_for_mutation;delete_resource_quota | block | True |
| S06_safe_rollout_undo | rollout_undo | allow | - | allow | True |

## Next step

Replace offline action summaries with replay output from minikube/k3s, then compare unsafe action block rate, false reject rate, and recovery time.