#!/usr/bin/env python3
"""
T12 offline batching-fairness simulator.

This is NOT a real vLLM experiment.
It is a deterministic offline smoke simulator for:
- victim SLO degradation under adversarial tenants
- simple tenant-aware guard policies

The real vLLM/SGLang experiment should later reuse the same workload profile.
"""

import argparse
import csv
import json
import math
import random
import statistics
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Request:
    req_id: str
    tenant_id: str
    kind: str
    arrival_ms: float
    prompt_tokens: int
    output_tokens: int
    ttft_slo_ms: float
    remaining_decode_tokens: int
    admitted_ms: Optional[float] = None
    first_token_ms: Optional[float] = None
    finish_ms: Optional[float] = None


@dataclass
class SimResult:
    policy: str
    attack_type: str
    adv_load: float
    seed: int
    victim_n: int
    victim_ttft_p50_ms: float
    victim_ttft_p95_ms: float
    victim_ttft_mean_ms: float
    victim_slo_violation_rate: float
    victim_max_ttft_ms: float
    all_finished_n: int
    total_requests: int


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def positive_int(rng: random.Random, mean: float, jitter: float, low: int = 1) -> int:
    value = int(round(rng.gauss(mean, jitter)))
    return max(low, value)


def poisson_arrivals(rng: random.Random, rate_rps: float, duration_s: float) -> List[float]:
    if rate_rps <= 0:
        return []
    t = 0.0
    arrivals = []
    while t < duration_s:
        t += rng.expovariate(rate_rps)
        if t < duration_s:
            arrivals.append(t * 1000.0)
    return arrivals


def generate_requests(profile: dict, attack_type: str, adv_load: float, seed: int) -> List[Request]:
    rng = random.Random(seed)
    sim = profile["simulator"]
    duration_s = float(sim["duration_s"])

    victim_cfg = profile["victim"]
    adv_cfg = profile["adversaries"][attack_type]

    requests: List[Request] = []

    victim_arrivals = poisson_arrivals(rng, float(victim_cfg["arrival_rate_rps"]), duration_s)
    for i, arr in enumerate(victim_arrivals):
        p = positive_int(rng, victim_cfg["prompt_tokens_mean"], victim_cfg["prompt_tokens_jitter"])
        o = positive_int(rng, victim_cfg["output_tokens_mean"], victim_cfg["output_tokens_jitter"])
        requests.append(Request(
            req_id=f"victim-{i:05d}",
            tenant_id="victim",
            kind="victim",
            arrival_ms=arr,
            prompt_tokens=p,
            output_tokens=o,
            remaining_decode_tokens=o,
            ttft_slo_ms=float(victim_cfg["ttft_slo_ms"]),
        ))

    # adversarial load is relative to victim base arrival rate
    adv_rate = float(victim_cfg["arrival_rate_rps"]) * float(adv_load)

    if attack_type == "burst":
        # Bursty attack: same mean load, but clustered arrivals.
        burst_count = max(1, int(duration_s / 6))
        req_idx = 0
        for b in range(burst_count):
            center_ms = (b * 6.0 + rng.uniform(0.0, 2.0)) * 1000.0
            burst_size = max(1, int(round(adv_rate * 6.0)))
            for _ in range(burst_size):
                arr = min(duration_s * 1000.0 - 1.0, center_ms + rng.uniform(0, 400))
                p = positive_int(rng, adv_cfg["prompt_tokens_mean"], adv_cfg["prompt_tokens_jitter"])
                o = positive_int(rng, adv_cfg["output_tokens_mean"], adv_cfg["output_tokens_jitter"])
                requests.append(Request(
                    req_id=f"{adv_cfg['tenant_id']}-{req_idx:05d}",
                    tenant_id=adv_cfg["tenant_id"],
                    kind="adversary",
                    arrival_ms=arr,
                    prompt_tokens=p,
                    output_tokens=o,
                    remaining_decode_tokens=o,
                    ttft_slo_ms=float(adv_cfg["ttft_slo_ms"]),
                ))
                req_idx += 1
    else:
        adv_arrivals = poisson_arrivals(rng, adv_rate, duration_s)
        for i, arr in enumerate(adv_arrivals):
            p = positive_int(rng, adv_cfg["prompt_tokens_mean"], adv_cfg["prompt_tokens_jitter"])
            o = positive_int(rng, adv_cfg["output_tokens_mean"], adv_cfg["output_tokens_jitter"])
            requests.append(Request(
                req_id=f"{adv_cfg['tenant_id']}-{i:05d}",
                tenant_id=adv_cfg["tenant_id"],
                kind="adversary",
                arrival_ms=arr,
                prompt_tokens=p,
                output_tokens=o,
                remaining_decode_tokens=o,
                ttft_slo_ms=float(adv_cfg["ttft_slo_ms"]),
            ))

    requests.sort(key=lambda r: (r.arrival_ms, r.req_id))
    return requests


def prefill_cost_ms(req: Request, profile: dict) -> float:
    sim = profile["simulator"]
    return float(sim["prefill_base_ms"]) + float(sim["prefill_ms_per_token"]) * req.prompt_tokens


def decode_step_cost_ms(active_n: int, profile: dict) -> float:
    sim = profile["simulator"]
    return float(sim["decode_base_ms"]) + float(sim["decode_ms_per_active_sequence"]) * max(1, active_n)


def percentile(values: List[float], p: float) -> float:
    if not values:
        return float("nan")
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return values[int(k)]
    return values[lo] * (hi - k) + values[hi] * (k - lo)


def select_next_request(policy: str, queue: List[Request], now_ms: float, guard_state: dict) -> Optional[int]:
    if not queue:
        return None

    if policy == "baseline_fcfs":
        return 0

    if policy == "victim_priority_guard":
        # Simple tenant-aware guard: if victim has waited, admit victim first.
        for i, req in enumerate(queue):
            if req.tenant_id == "victim":
                return i
        return 0

    if policy == "token_budget_guard":
        # Budget adversarial prefill tokens per epoch. Victim is always allowed.
        epoch_ms = 2000.0
        budget_tokens = 2048

        epoch = int(now_ms // epoch_ms)
        if guard_state.get("epoch") != epoch:
            guard_state["epoch"] = epoch
            guard_state["adv_prefill_tokens"] = 0

        for i, req in enumerate(queue):
            if req.tenant_id == "victim":
                return i

        for i, req in enumerate(queue):
            used = int(guard_state.get("adv_prefill_tokens", 0))
            if used + req.prompt_tokens <= budget_tokens:
                guard_state["adv_prefill_tokens"] = used + req.prompt_tokens
                return i

        # If all adversary requests exceed budget, wait for next epoch.
        return None

    raise ValueError(f"unknown policy: {policy}")


def simulate(profile: dict, attack_type: str, adv_load: float, policy: str, seed: int) -> SimResult:
    requests = generate_requests(profile, attack_type, adv_load, seed)
    max_active = int(profile["simulator"]["max_active_sequences"])

    pending = list(requests)
    queue: List[Request] = []
    active: List[Request] = []
    finished: List[Request] = []
    now_ms = 0.0
    guard_state: Dict[str, int] = {}

    # Continue until all requests are finished or a conservative cap is reached.
    hard_stop_ms = float(profile["simulator"]["duration_s"]) * 1000.0 + 300000.0

    while (pending or queue or active) and now_ms < hard_stop_ms:
        while pending and pending[0].arrival_ms <= now_ms:
            queue.append(pending.pop(0))

        admitted_any = False
        while len(active) < max_active and queue:
            idx = select_next_request(policy, queue, now_ms, guard_state)
            if idx is None:
                break

            req = queue.pop(idx)
            if req.arrival_ms > now_ms:
                queue.insert(idx, req)
                break

            req.admitted_ms = now_ms
            now_ms += prefill_cost_ms(req, profile)
            req.first_token_ms = now_ms
            active.append(req)
            admitted_any = True

            while pending and pending[0].arrival_ms <= now_ms:
                queue.append(pending.pop(0))

        if active:
            step_cost = decode_step_cost_ms(len(active), profile)
            now_ms += step_cost

            still_active: List[Request] = []
            for req in active:
                req.remaining_decode_tokens -= 1
                if req.remaining_decode_tokens <= 0:
                    req.finish_ms = now_ms
                    finished.append(req)
                else:
                    still_active.append(req)
            active = still_active

            while pending and pending[0].arrival_ms <= now_ms:
                queue.append(pending.pop(0))

        elif pending:
            # Jump to next arrival when idle.
            now_ms = max(now_ms, pending[0].arrival_ms)
        elif queue and not admitted_any:
            # Budget guard blocked adversary-only queue; jump to next budget epoch.
            now_ms = (int(now_ms // 2000.0) + 1) * 2000.0
        else:
            break

    victim_finished = [r for r in finished if r.tenant_id == "victim" and r.first_token_ms is not None]
    ttfts = [r.first_token_ms - r.arrival_ms for r in victim_finished]
    violations = [t > victim_finished[i].ttft_slo_ms for i, t in enumerate(ttfts)]

    return SimResult(
        policy=policy,
        attack_type=attack_type,
        adv_load=adv_load,
        seed=seed,
        victim_n=len(victim_finished),
        victim_ttft_p50_ms=percentile(ttfts, 0.50),
        victim_ttft_p95_ms=percentile(ttfts, 0.95),
        victim_ttft_mean_ms=statistics.mean(ttfts) if ttfts else float("nan"),
        victim_slo_violation_rate=(sum(violations) / len(violations)) if violations else float("nan"),
        victim_max_ttft_ms=max(ttfts) if ttfts else float("nan"),
        all_finished_n=len(finished),
        total_requests=len(requests),
    )


def write_csv(results: List[SimResult], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(SimResult.__dataclass_fields__.keys()) + [
        "track_id",
        "git_commit",
        "timestamp",
        "fabricated_results",
        "synthetic_simulation",
        "real_vllm_experiment",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            row = {
                **r.__dict__,
                "track_id": "T12",
                "git_commit": git_commit(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fabricated_results": False,
                "synthetic_simulation": True,
                "real_vllm_experiment": False,
            }
            writer.writerow(row)


def write_md(results: List[SimResult], out_md: Path) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# T12 Offline Batching-Fairness Smoke",
        "",
        "This is an offline simulator, not a real vLLM experiment.",
        "",
        "## Goal",
        "",
        "Measure whether adversarial tenant workloads can increase victim TTFT SLO violation, and whether simple tenant-aware guards reduce the effect.",
        "",
        "## Best smoke rows",
        "",
        "| attack | adv_load | policy | victim_n | p95 TTFT ms | SLO violation rate |",
        "|---|---:|---|---:|---:|---:|",
    ]

    # show highest load for each attack/policy
    for r in sorted(results, key=lambda x: (x.attack_type, x.policy, x.adv_load)):
        if abs(r.adv_load - 2.0) < 1e-9:
            lines.append(
                f"| {r.attack_type} | {r.adv_load:.2f} | {r.policy} | "
                f"{r.victim_n} | {r.victim_ttft_p95_ms:.2f} | {r.victim_slo_violation_rate:.3f} |"
            )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- `baseline_fcfs` is the no-protection baseline.",
        "- `victim_priority_guard` represents a simple latency-sensitive tenant preference.",
        "- `token_budget_guard` represents a simple per-epoch adversarial prefill-token budget.",
        "- This result is only a smoke signal. It must later be validated against vLLM/SGLang real serving traces.",
        "",
        "## Next step",
        "",
        "Reuse the T11 OpenAI-compatible serving harness to replace simulated TTFT with real TTFT under mixed-tenant workloads.",
    ])

    out_md.write_text("\n".join(lines), encoding="utf-8")


def maybe_plot(results: List[SimResult], out_png: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not available; skip plot")
        return

    out_png.parent.mkdir(parents=True, exist_ok=True)

    attacks = sorted(set(r.attack_type for r in results))
    policies = ["baseline_fcfs", "victim_priority_guard", "token_budget_guard"]

    for attack in attacks:
        plt.figure(figsize=(7.5, 4.5))
        for policy in policies:
            rows = sorted(
                [r for r in results if r.attack_type == attack and r.policy == policy],
                key=lambda r: r.adv_load,
            )
            if not rows:
                continue
            x = [r.adv_load for r in rows]
            y = [r.victim_slo_violation_rate for r in rows]
            plt.plot(x, y, marker="o", label=policy)

        plt.xlabel("Adversarial tenant load ratio")
        plt.ylabel("Victim TTFT SLO violation rate")
        plt.title(f"T12 offline smoke: {attack}")
        plt.ylim(-0.02, 1.02)
        plt.legend()
        plt.tight_layout()
        attack_png = out_png.with_name(out_png.stem + f"_{attack}" + out_png.suffix)
        plt.savefig(attack_png, dpi=180)
        print(f"Wrote plot to {attack_png}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", default="tracks/T12_llm_batch_fairness/workloads/t12_tenant_profiles.json")
    parser.add_argument("--out-csv", default="tracks/T12_llm_batch_fairness/results/smoke/t12_offline_batch_slo.csv")
    parser.add_argument("--out-md", default="refine-logs/socc26/T12_OFFLINE_BATCH_SMOKE.md")
    parser.add_argument("--out-png", default="tracks/T12_llm_batch_fairness/figures/t12_slo_violation_vs_adv_load.png")
    parser.add_argument("--seeds", default="20260626,20260627,20260628")
    args = parser.parse_args()

    profile = json.loads(Path(args.profiles).read_text(encoding="utf-8-sig"))
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    attack_types = ["long_prompt", "long_decode", "burst"]
    adv_loads = [0.0, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00]
    policies = ["baseline_fcfs", "victim_priority_guard", "token_budget_guard"]

    raw_results: List[SimResult] = []

    for seed in seeds:
        for attack in attack_types:
            for load in adv_loads:
                for policy in policies:
                    raw_results.append(simulate(profile, attack, load, policy, seed))

    # Aggregate by averaging over seeds.
    grouped: Dict[Tuple[str, str, float], List[SimResult]] = {}
    for r in raw_results:
        grouped.setdefault((r.policy, r.attack_type, r.adv_load), []).append(r)

    aggregated: List[SimResult] = []
    for (policy, attack, load), rows in sorted(grouped.items()):
        aggregated.append(SimResult(
            policy=policy,
            attack_type=attack,
            adv_load=load,
            seed=-1,
            victim_n=int(round(statistics.mean(r.victim_n for r in rows))),
            victim_ttft_p50_ms=statistics.mean(r.victim_ttft_p50_ms for r in rows),
            victim_ttft_p95_ms=statistics.mean(r.victim_ttft_p95_ms for r in rows),
            victim_ttft_mean_ms=statistics.mean(r.victim_ttft_mean_ms for r in rows),
            victim_slo_violation_rate=statistics.mean(r.victim_slo_violation_rate for r in rows),
            victim_max_ttft_ms=statistics.mean(r.victim_max_ttft_ms for r in rows),
            all_finished_n=int(round(statistics.mean(r.all_finished_n for r in rows))),
            total_requests=int(round(statistics.mean(r.total_requests for r in rows))),
        ))

    write_csv(aggregated, Path(args.out_csv))
    write_md(aggregated, Path(args.out_md))
    maybe_plot(aggregated, Path(args.out_png))

    print(f"Wrote CSV to {args.out_csv}")
    print(f"Wrote note to {args.out_md}")
    print(json.dumps([r.__dict__ for r in aggregated[:6]], indent=2))


if __name__ == "__main__":
    main()
