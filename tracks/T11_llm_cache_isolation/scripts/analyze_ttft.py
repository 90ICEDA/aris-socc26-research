#!/usr/bin/env python3
"""
Analyze T11 smoke latency results.

Outputs:
- CSV summary by condition
- Markdown go/no-go note
- Optional PNG figure if matplotlib is installed
"""

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Any


def load_results(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if row.get("warmup"):
                    continue
                if row.get("error"):
                    continue
                if row.get("ttft_ms") is None:
                    continue
                rows.append(row)
    return rows


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


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    groups: Dict[str, List[float]] = {}
    for r in rows:
        groups.setdefault(r["condition"], []).append(float(r["ttft_ms"]))

    summary = {}
    for cond, vals in sorted(groups.items()):
        summary[cond] = {
            "n": len(vals),
            "ttft_ms_mean": statistics.mean(vals),
            "ttft_ms_median": statistics.median(vals),
            "ttft_ms_p05": percentile(vals, 0.05),
            "ttft_ms_p25": percentile(vals, 0.25),
            "ttft_ms_p75": percentile(vals, 0.75),
            "ttft_ms_p95": percentile(vals, 0.95),
            "ttft_ms_min": min(vals),
            "ttft_ms_max": max(vals),
        }
    return summary


def write_csv(summary: Dict[str, Dict[str, float]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "condition",
        "n",
        "ttft_ms_mean",
        "ttft_ms_median",
        "ttft_ms_p05",
        "ttft_ms_p25",
        "ttft_ms_p75",
        "ttft_ms_p95",
        "ttft_ms_min",
        "ttft_ms_max",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for cond, stats in summary.items():
            row = {"condition": cond}
            row.update(stats)
            writer.writerow(row)


def write_note(summary: Dict[str, Dict[str, float]], out_md: Path) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)

    o0 = summary.get("overlap_0", {})
    o100 = summary.get("overlap_100", {})

    median0 = o0.get("ttft_ms_median", float("nan"))
    median100 = o100.get("ttft_ms_median", float("nan"))
    p950 = o0.get("ttft_ms_p95", float("nan"))
    p95100 = o100.get("ttft_ms_p95", float("nan"))

    delta_median = median0 - median100
    delta_p95 = p950 - p95100

    decision = "UNDECIDED"
    if not math.isnan(delta_median):
        # This is a loose smoke criterion. We will tighten later.
        if abs(delta_median) >= 20 or abs(delta_p95) >= 50:
            decision = "GO: measurable TTFT separation exists in smoke run"
        else:
            decision = "NO-GO for this setup: separation is weak; try longer prefixes, more samples, or quieter GPU"

    lines = [
        "# T11 GO / NO-GO Smoke Note",
        "",
        "## Summary",
        "",
        f"- overlap_0 median TTFT: {median0:.3f} ms",
        f"- overlap_100 median TTFT: {median100:.3f} ms",
        f"- median delta overlap_0 - overlap_100: {delta_median:.3f} ms",
        f"- p95 delta overlap_0 - overlap_100: {delta_p95:.3f} ms",
        f"- decision: {decision}",
        "",
        "## Raw condition stats",
        "",
        "| condition | n | median TTFT ms | p95 TTFT ms | mean TTFT ms |",
        "|---|---:|---:|---:|---:|",
    ]

    for cond, stats in summary.items():
        lines.append(
            f"| {cond} | {int(stats['n'])} | "
            f"{stats['ttft_ms_median']:.3f} | "
            f"{stats['ttft_ms_p95']:.3f} | "
            f"{stats['ttft_ms_mean']:.3f} |"
        )

    lines.extend([
        "",
        "## Notes",
        "",
        "- This is smoke evidence only, not a final claim.",
        "- Results are synthetic and manifest-backed.",
        "- If separation is weak, increase context length and sample count before abandoning the track.",
    ])

    out_md.write_text("\n".join(lines), encoding="utf-8")


def maybe_plot(rows: List[Dict[str, Any]], out_png: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not installed; skipping plot")
        return

    groups: Dict[str, List[float]] = {}
    for r in rows:
        groups.setdefault(r["condition"], []).append(float(r["ttft_ms"]))

    labels = sorted(groups.keys())
    data = [groups[l] for l in labels]

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7, 4))
    plt.boxplot(data, tick_labels=labels, showmeans=True)
    plt.ylabel("TTFT (ms)")
    plt.title("T11 Prefix-overlap smoke TTFT")
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    print(f"Wrote plot to {out_png}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="tracks/T11_llm_cache_isolation/results/smoke/t11_smoke_latency.jsonl")
    parser.add_argument("--out-csv", default="tracks/T11_llm_cache_isolation/results/smoke/t11_smoke_summary.csv")
    parser.add_argument("--out-md", default="refine-logs/socc26/T11_GO_NOGO.md")
    parser.add_argument("--out-png", default="tracks/T11_llm_cache_isolation/figures/t11_ttft_smoke.png")
    args = parser.parse_args()

    rows = load_results(Path(args.input))
    if not rows:
        raise SystemExit("No valid non-warmup rows found. Check errors in result JSONL.")

    summary = summarize(rows)
    write_csv(summary, Path(args.out_csv))
    write_note(summary, Path(args.out_md))
    maybe_plot(rows, Path(args.out_png))

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote CSV to {args.out_csv}")
    print(f"Wrote note to {args.out_md}")


if __name__ == "__main__":
    main()
