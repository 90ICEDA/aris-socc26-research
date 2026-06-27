#!/usr/bin/env python3
"""
T13 Kubernetes replay smoke.

This script uses a real local Kubernetes cluster, e.g. kind-t13-replay.

It creates isolated replay namespaces, installs minimal baseline resources,
validates candidate actions through kubectl/server-side dry-run or target lookup,
then applies the existing ReplayGuard-style contract gate.

Safety:
- Only creates resources in namespaces prefixed with t13-replay-.
- Does not execute destructive proposed actions.
- Delete/evict actions are checked by target lookup, not executed.
"""

import argparse
import csv
import json
import re
import subprocess
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple


MUTATING_ACTIONS = {
    "restart_deployment",
    "patch_hpa",
    "delete_network_policy",
    "evict_gpu_job",
    "delete_resource_quota",
    "rollout_undo",
}


def run(cmd: List[str], check: bool = False) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise RuntimeError(
            "command failed\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout:\n{p.stdout}\n"
            f"stderr:\n{p.stderr}\n"
        )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def git_commit() -> str:
    rc, out, _ = run(["git", "rev-parse", "HEAD"])
    return out if rc == 0 else "unknown"


def sanitize_name(s: str, max_len: int = 50) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len].strip("-") or "x"


def target_name(target: str, default: str) -> str:
    if "/" in target:
        return target.split("/", 1)[1]
    return default


def evaluate_scenario(scenario: dict, contracts: dict) -> Tuple[str, List[str]]:
    action = scenario["proposed_action"]
    incident = scenario["incident"]
    rules = contracts["contracts"]
    violations = []

    action_type = action.get("action_type")
    critical = bool(incident.get("critical", False))
    after = int(action.get("expected_replicas_after", incident.get("current_replicas", 0)))
    blast = action.get("blast_radius_namespaces", []) or []

    if rules.get("rollback_required_for_mutation", True):
        if action_type in MUTATING_ACTIONS and not action.get("has_rollback", False):
            violations.append("rollback_required_for_mutation")

    if critical:
        min_rep = int(rules.get("critical_service_min_replicas", 2))
        if after < min_rep:
            violations.append(f"critical_service_min_replicas<{min_rep}")

    max_blast = int(rules.get("max_blast_radius_namespaces", 1))
    if len(set(blast)) > max_blast:
        violations.append(f"blast_radius_namespaces>{max_blast}")

    if rules.get("deny_delete_default_deny_network_policy", True):
        target = action.get("target", "")
        if action_type == "delete_network_policy" and "default-deny" in target:
            violations.append("delete_default_deny_network_policy")

    if rules.get("deny_delete_resource_quota", True):
        if action_type == "delete_resource_quota":
            violations.append("delete_resource_quota")

    if rules.get("deny_gpu_eviction_without_pdb", True):
        if action_type == "evict_gpu_job" and not action.get("has_pdb", False):
            violations.append("gpu_eviction_without_pdb")

    return ("allow" if not violations else "block"), violations


def baseline_manifest(namespace: str, scenario: dict) -> str:
    incident = scenario["incident"]
    action = scenario["proposed_action"]

    service = sanitize_name(str(incident.get("service", "app")))
    deployment = sanitize_name(target_name(action.get("target", ""), service))
    replicas = max(1, int(incident.get("current_replicas", 1)))

    docs = []

    docs.append(f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {deployment}
  namespace: {namespace}
  labels:
    app: {deployment}
    t13.replayguard/baseline: "true"
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {deployment}
  template:
    metadata:
      labels:
        app: {deployment}
    spec:
      containers:
      - name: pause
        image: registry.k8s.io/pause:3.10
        imagePullPolicy: IfNotPresent
""")

    docs.append(f"""
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: {namespace}
  labels:
    t13.replayguard/baseline: "true"
spec:
  podSelector: {{}}
  policyTypes:
  - Ingress
  - Egress
""")

    docs.append(f"""
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a-quota
  namespace: {namespace}
  labels:
    t13.replayguard/baseline: "true"
spec:
  hard:
    pods: "20"
    requests.cpu: "2"
    requests.memory: 2Gi
""")

    docs.append(f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: long-train-42
  namespace: {namespace}
  labels:
    app: long-train-42
    t13.replayguard/baseline: "true"
spec:
  template:
    metadata:
      labels:
        app: long-train-42
    spec:
      restartPolicy: Never
      containers:
      - name: pause
        image: registry.k8s.io/pause:3.10
        imagePullPolicy: IfNotPresent
""")

    return "\n---\n".join(textwrap.dedent(d).strip() for d in docs) + "\n"


def candidate_manifest(namespace: str, scenario: dict) -> str:
    incident = scenario["incident"]
    action = scenario["proposed_action"]
    action_type = action.get("action_type")
    service = sanitize_name(str(incident.get("service", "app")))
    deployment = sanitize_name(target_name(action.get("target", ""), service))
    expected_replicas = max(1, int(action.get("expected_replicas_after", incident.get("current_replicas", 1))))

    if action_type in {"restart_deployment", "rollout_undo"}:
        return textwrap.dedent(f"""
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: {deployment}
          namespace: {namespace}
          annotations:
            t13.replayguard/action: "{action_type}"
            t13.replayguard/dry-run: "server"
          labels:
            app: {deployment}
        spec:
          replicas: {expected_replicas}
          selector:
            matchLabels:
              app: {deployment}
          template:
            metadata:
              labels:
                app: {deployment}
              annotations:
                t13.replayguard/replayed-at: "{datetime.now(timezone.utc).isoformat()}"
            spec:
              containers:
              - name: pause
                image: registry.k8s.io/pause:3.10
                imagePullPolicy: IfNotPresent
        """).strip() + "\n"

    if action_type == "patch_hpa":
        hpa_name = sanitize_name(target_name(action.get("target", ""), service))
        return textwrap.dedent(f"""
        apiVersion: autoscaling/v2
        kind: HorizontalPodAutoscaler
        metadata:
          name: {hpa_name}
          namespace: {namespace}
          annotations:
            t13.replayguard/action: "patch_hpa"
        spec:
          minReplicas: {expected_replicas}
          maxReplicas: 10
          scaleTargetRef:
            apiVersion: apps/v1
            kind: Deployment
            name: {deployment}
          metrics:
          - type: Resource
            resource:
              name: cpu
              target:
                type: Utilization
                averageUtilization: 60
        """).strip() + "\n"

    return ""


def kubectl_apply_manifest(manifest: str, dry_run_server: bool = False) -> Tuple[int, str, str]:
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml", encoding="utf-8") as f:
        f.write(manifest)
        path = f.name

    cmd = ["kubectl", "apply", "-f", path]
    if dry_run_server:
        cmd.extend(["--dry-run=server", "-o", "yaml"])

    return run(cmd)


def kubectl_get_target(namespace: str, action_type: str, target: str) -> Tuple[int, str, str, str]:
    if action_type == "delete_network_policy":
        resource = "networkpolicy"
        name = target_name(target, "default-deny")
    elif action_type == "delete_resource_quota":
        resource = "resourcequota"
        name = target_name(target, "team-a-quota")
    elif action_type == "evict_gpu_job":
        resource = "job"
        name = target_name(target, "long-train-42")
    else:
        resource = "deployment"
        name = target_name(target, "app")

    cmd = ["kubectl", "get", resource, sanitize_name(name), "-n", namespace, "-o", "name"]
    rc, out, err = run(cmd)
    return rc, out, err, " ".join(cmd)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default="tracks/T13_cloudops_replay_guard/scenarios/t13_scenarios.json")
    parser.add_argument("--contracts", default="tracks/T13_cloudops_replay_guard/contracts/t13_contracts.json")
    parser.add_argument("--out-csv", default="tracks/T13_cloudops_replay_guard/results/smoke/t13_k8s_replay_gate_table.csv")
    parser.add_argument("--out-md", default="refine-logs/socc26/T13_K8S_REPLAY_SMOKE.md")
    parser.add_argument("--cleanup", action="store_true", help="Delete replay namespaces at the end")
    args = parser.parse_args()

    scenarios = json.loads(Path(args.scenarios).read_text(encoding="utf-8-sig"))
    contracts = json.loads(Path(args.contracts).read_text(encoding="utf-8-sig"))

    rc, context, context_err = run(["kubectl", "config", "current-context"])
    if rc != 0:
        raise SystemExit(f"kubectl context is not set: {context_err}")

    rc, nodes, nodes_err = run(["kubectl", "get", "nodes", "-o", "name"])
    if rc != 0:
        raise SystemExit(f"kubectl cannot reach cluster: {nodes_err}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rows = []
    namespaces = []

    for scenario in scenarios:
        sid = scenario["scenario_id"]
        ns = sanitize_name(f"t13-replay-{sid}-{run_id}", max_len=63)
        namespaces.append(ns)

        run(["kubectl", "create", "namespace", ns], check=True)
        run(["kubectl", "label", "namespace", ns, f"t13.replayguard/run={run_id}", "--overwrite"], check=True)
        run(["kubectl", "label", "namespace", ns, f"t13.replayguard/scenario={sanitize_name(sid)}", "--overwrite"], check=True)

        base_manifest = baseline_manifest(ns, scenario)
        base_rc, base_out, base_err = kubectl_apply_manifest(base_manifest, dry_run_server=False)

        action = scenario["proposed_action"]
        action_type = action.get("action_type", "")
        target = action.get("target", "")

        manifest = candidate_manifest(ns, scenario)
        if manifest:
            api_validation_mode = "kubectl_apply_server_dry_run"
            candidate_rc, candidate_out, candidate_err = kubectl_apply_manifest(manifest, dry_run_server=True)
            candidate_command = "kubectl apply --dry-run=server -f <candidate-manifest>"
        else:
            api_validation_mode = "kubectl_get_existing_target_no_delete"
            candidate_rc, candidate_out, candidate_err, candidate_command = kubectl_get_target(ns, action_type, target)

        gate, violations = evaluate_scenario(scenario, contracts)

        rows.append({
            "track_id": "T13",
            "run_id": f"t13_k8s_replay_{run_id}_{sid}",
            "git_commit": git_commit(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fabricated_results": False,
            "synthetic_scenario": True,
            "real_cluster_execution": True,
            "destructive_action_executed": False,
            "kubectl_context": context,
            "node_names": nodes.replace("\n", ";"),
            "namespace": ns,
            "scenario_id": sid,
            "title": scenario["title"],
            "action_type": action_type,
            "target": target,
            "api_baseline_apply_ok": base_rc == 0,
            "api_candidate_validation_ok": candidate_rc == 0,
            "api_validation_mode": api_validation_mode,
            "candidate_command": candidate_command,
            "candidate_stdout_preview": candidate_out[:240].replace("\n", " "),
            "candidate_stderr_preview": candidate_err[:240].replace("\n", " "),
            "gate": gate,
            "expected_gate": scenario.get("expected_gate", ""),
            "matches_expected": gate == scenario.get("expected_gate", ""),
            "violations": ";".join(violations) if violations else "",
        })

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    fields = list(rows[0].keys())
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    allowed = sum(1 for r in rows if r["gate"] == "allow")
    blocked = sum(1 for r in rows if r["gate"] == "block")
    api_ok = sum(1 for r in rows if r["api_candidate_validation_ok"])
    matched = sum(1 for r in rows if r["matches_expected"])

    md = [
        "# T13 Kubernetes Replay Smoke",
        "",
        "This run uses a real local Kubernetes cluster, but it does not execute destructive proposed actions.",
        "",
        "## Summary",
        "",
        f"- kubectl context: `{context}`",
        f"- run id: `{run_id}`",
        f"- total scenarios: {total}",
        f"- allowed: {allowed}",
        f"- blocked: {blocked}",
        f"- API candidate validations ok: {api_ok}/{total}",
        f"- expected-match count: {matched}/{total}",
        "",
        "## Replay table",
        "",
        "| scenario | namespace | action | API validation | gate | violations | expected | match |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in rows:
        md.append(
            f"| {r['scenario_id']} | `{r['namespace']}` | {r['action_type']} | "
            f"{r['api_candidate_validation_ok']} | {r['gate']} | "
            f"{r['violations'] or '-'} | {r['expected_gate']} | {r['matches_expected']} |"
        )

    md.extend([
        "",
        "## Cleanup",
        "",
        "Replay namespaces are labeled by run id. To delete them:",
        "",
        f"`kubectl delete namespace -l t13.replayguard/run={run_id}`",
    ])

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"Wrote CSV to {out_csv}")
    print(f"Wrote note to {out_md}")

    if args.cleanup:
        for ns in namespaces:
            run(["kubectl", "delete", "namespace", ns, "--wait=false"])


if __name__ == "__main__":
    main()
