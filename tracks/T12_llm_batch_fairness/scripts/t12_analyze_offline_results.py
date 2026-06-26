#!/usr/bin/env python3
"""
T12 offline result interpretation.

Input:
  tracks/T12_llm_batch_fairness/results/smoke/t12_offline_batch_slo.csv

Output:
  - p95 TTFT plots for each attack type
  - interpretation markdown note

This is not a real vLLM/SGLang experiment.
"""

import argparse
import csv
from pathlib import Path


def load_rows(path: Path):
    rows = []
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            for k in [
                "adv_load",
                "victim_ttft_p95_ms",
                "victim_slo_violation_rate",
                "victim_ttft_mean_ms",
                "victim_max_ttft_ms",
            ]:
                r[k] = float(r[k])
            rows.append(r)
    return rows


def plot_p95(rows, out_dir: Path):
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)

    attacks = sorted(set(r["attack_type"] for r in rows))
    policies = ["baseline_fcfs", "victim_priority_guard", "token_budget_guard"]

    for attack in attacks:
        plt.figure(figsize=(7.5, 4.5))

        for policy in policies:
            sub = sorted(
                [r for r in rows if r["attack_type"] == attack and r["policy"] == policy],
                key=lambda r: r["adv_load"],
            )
            if not sub:
                continue

            x = [r["adv_load"] for r in sub]
            y = [r["victim_ttft_p95_ms"] for r in sub]
            plt.plot(x, y, marker="o", label=policy)

        plt.axhline(800, linestyle="--", linewidth=1, label="victim TTFT SLO")
        plt.xlabel("Adversarial tenant load ratio")
        plt.ylabel("Victim p95 TTFT (ms)")
        plt.title(f"T12 offline smoke p95 TTFT: {attack}")
        plt.legend()
        plt.tight_layout()

        out = out_dir / f"t12_p95_ttft_vs_adv_load_{attack}.png"
        plt.savefig(out, dpi=180)
        print(f"Wrote {out}")


def write_note(rows, out_md: Path):
    out_md.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# T12 Offline Smoke Interpretation v1",
        "",
        "This note interprets the offline simulator output. It is not a real vLLM/SGLang measurement.",
        "",
        "## Main conclusion",
        "",
        "- `long_decode` is the strongest current signal: baseline FCFS shows rapidly increasing victim TTFT SLO violation as adversarial load increases.",
        "- `token_budget_guard` reduces but does not eliminate long-decode interference.",
        "- `long_prompt` currently shows zero SLO violation under the current parameters, so it should be treated as a weak or negative signal, not the main story.",
        "",
        "## Highest-load rows",
        "",
        "| attack | policy | adv_load | victim p95 TTFT ms | victim mean TTFT ms | victim max TTFT ms | SLO violation |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]

    for attack in sorted(set(r["attack_type"] for r in rows)):
        for policy in sorted(set(r["policy"] for r in rows)):
            sub = [r for r in rows if r["attack_type"] == attack and r["policy"] == policy]
            if not sub:
                continue
            r = max(sub, key=lambda x: x["adv_load"])
            lines.append(
                f"| {r['attack_type']} | {r['policy']} | {r['adv_load']:.2f} | "
                f"{r['victim_ttft_p95_ms']:.2f} | {r['victim_ttft_mean_ms']:.2f} | "
                f"{r['victim_max_ttft_ms']:.2f} | {r['victim_slo_violation_rate']:.3f} |"
            )

    lines.extend([
        "",
        "## Paper pivot",
        "",
        "T12 should focus on decode-slot occupancy rather than generic long-request abuse.",
        "",
        "Proposed framing:",
        "",
        "> Existing continuous batching improves throughput, but strategic long-decode tenants can monopolize active decode slots and break latency SLOs for short interactive tenants.",
        "",
        "## Next real-system experiment",
        "",
        "1. Port only the long-decode workload to real vLLM/SGLang first.",
        "2. Measure victim TTFT, TBT/TPOT, P95/P99, and SLO violation.",
        "3. Compare baseline FCFS against per-tenant max active sequences, output-token budget, and admission shaping.",
    ])

    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_md}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="tracks/T12_llm_batch_fairness/results/smoke/t12_offline_batch_slo.csv")
    parser.add_argument("--out-dir", default="tracks/T12_llm_batch_fairness/figures")
    parser.add_argument("--out-md", default="refine-logs/socc26/T12_OFFLINE_INTERPRETATION_V1.md")
    args = parser.parse_args()

    rows = load_rows(Path(args.csv))
    plot_p95(rows, Path(args.out_dir))
    write_note(rows, Path(args.out_md))


if __name__ == "__main__":
    main()
