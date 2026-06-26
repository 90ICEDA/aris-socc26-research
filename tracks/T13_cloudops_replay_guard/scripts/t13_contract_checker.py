#!/usr/bin/env python3
"""
T13 ReplayGuard smoke checker.

This is an offline contract-gating smoke test.
It does not execute kubectl and does not mutate any real cluster.
"""

import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


MUTATING_ACTIONS = {
    "restart_deployment",
    "patch_hpa",
    "delete_network_policy",
    "evict_gpu_job",
    "delete_resource_quota",
    "rollout_undo",
}


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def evaluate_scenario(scenario: dict, contracts: dict) -> dict:
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

    allowed = len(violations) == 0

    return {
        "track_id": "T13",
        "run_id": f"t13_gate_{scenario['scenario_id']}",
        "git_commit": git_commit(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fabricated_results": False,
        "synthetic_scenario": True,
        "real_cluster_execution": False,
        "scenario_id": scenario["scenario_id"],
        "title": scenario["title"],
        "action_type": action_type,
        "target": action.get("target", ""),
        "description": action.get("description", ""),
        "allowed": allowed,
        "gate": "allow" if allowed else "block",
        "expected_gate": scenario.get("expected_gate", ""),
        "matches_expected": ("allow" if allowed else "block") == scenario.get("expected_gate", ""),
        "violations": ";".join(violations) if violations else "",
    }


def write_csv(rows, out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "track_id",
        "run_id",
        "git_commit",
        "timestamp",
        "fabricated_results",
        "synthetic_scenario",
        "real_cluster_execution",
        "scenario_id",
        "title",
        "action_type",
        "target",
        "description",
        "allowed",
        "gate",
        "expected_gate",
        "matches_expected",
        "violations",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_md(rows, out_md: Path) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)

    total = len(rows)
    blocked = sum(1 for r in rows if r["gate"] == "block")
    allowed = sum(1 for r in rows if r["gate"] == "allow")
    matched = sum(1 for r in rows if r["matches_expected"])

    lines = [
        "# T13 ReplayGuard Smoke Result",
        "",
        "This is an offline contract-gating smoke test. It does not execute kubectl and does not mutate a real cluster.",
        "",
        "## Summary",
        "",
        f"- total scenarios: {total}",
        f"- allowed: {allowed}",
        f"- blocked: {blocked}",
        f"- expected-match count: {matched}/{total}",
        "",
        "## Gate table",
        "",
        "| scenario | action | gate | violations | expected | match |",
        "|---|---|---|---|---|---|",
    ]

    for r in rows:
        violations = r["violations"] if r["violations"] else "-"
        lines.append(
            f"| {r['scenario_id']} | {r['action_type']} | {r['gate']} | "
            f"{violations} | {r['expected_gate']} | {r['matches_expected']} |"
        )

    lines.extend([
        "",
        "## Next step",
        "",
        "Replace offline action summaries with replay output from minikube/k3s, then compare unsafe action block rate, false reject rate, and recovery time.",
    ])

    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default="tracks/T13_cloudops_replay_guard/scenarios/t13_scenarios.json")
    parser.add_argument("--contracts", default="tracks/T13_cloudops_replay_guard/contracts/t13_contracts.json")
    parser.add_argument("--out-csv", default="tracks/T13_cloudops_replay_guard/results/smoke/t13_contract_gate_table.csv")
    parser.add_argument("--out-md", default="refine-logs/socc26/T13_CONTRACT_GATE_SMOKE.md")
    args = parser.parse_args()

    scenarios = json.loads(Path(args.scenarios).read_text(encoding="utf-8-sig"))
    contracts = json.loads(Path(args.contracts).read_text(encoding="utf-8-sig"))

    rows = [evaluate_scenario(s, contracts) for s in scenarios]

    write_csv(rows, Path(args.out_csv))
    write_md(rows, Path(args.out_md))

    print(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"Wrote CSV to {args.out_csv}")
    print(f"Wrote note to {args.out_md}")


if __name__ == "__main__":
    main()
