#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
from statistics import mean, median

import matplotlib.pyplot as plt

def percentile(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return xs[int(k)]
    return xs[lo] * (hi - k) + xs[hi] * (k - lo)

def pick_ttft_ms(row):
    for key in ["ttft_ms", "time_to_first_token_ms", "latency_ttft_ms"]:
        if key in row and row[key] is not None:
            return float(row[key])

    if "ttft_s" in row and row["ttft_s"] is not None:
        return float(row["ttft_s"]) * 1000.0

    if "metrics" in row and isinstance(row["metrics"], dict):
        m = row["metrics"]
        for key in ["ttft_ms", "time_to_first_token_ms", "latency_ttft_ms"]:
            if key in m and m[key] is not None:
                return float(m[key])
        if "ttft_s" in m and m["ttft_s"] is not None:
            return float(m["ttft_s"]) * 1000.0

    return None

def level_key(cond):
    try:
        return int(str(cond).split("_")[-1])
    except Exception:
        return 999999

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-png", required=True)
    ap.add_argument("--max-ttft-ms", type=float, default=5000.0)
    args = ap.parse_args()

    groups = {}
    counts = {}

    total_rows = 0
    skipped_error = 0
    skipped_missing_ttft = 0
    skipped_outlier = 0

    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            total_rows += 1
            row = json.loads(line)

            if row.get("warmup") is True:
                continue

            cond = row.get("condition")
            if cond is None:
                rid = row.get("request_id") or row.get("id") or ""
                cond = rid.split("-")[0] if "-" in rid else "unknown"

            counts.setdefault(cond, {
                "total": 0,
                "used": 0,
                "skipped_error": 0,
                "skipped_missing_ttft": 0,
                "skipped_outlier": 0,
            })
            counts[cond]["total"] += 1

            err = row.get("error")
            if err not in [None, "", "None"]:
                skipped_error += 1
                counts[cond]["skipped_error"] += 1
                continue

            ttft = pick_ttft_ms(row)
            if ttft is None:
                skipped_missing_ttft += 1
                counts[cond]["skipped_missing_ttft"] += 1
                continue

            if ttft <= 0 or ttft > args.max_ttft_ms:
                skipped_outlier += 1
                counts[cond]["skipped_outlier"] += 1
                continue

            groups.setdefault(cond, []).append(ttft)
            counts[cond]["used"] += 1

    rows = []
    for cond in sorted(groups, key=level_key):
        xs = groups[cond]
        rows.append({
            "condition": cond,
            "n": len(xs),
            "total": counts[cond]["total"],
            "skipped_error": counts[cond]["skipped_error"],
            "skipped_missing_ttft": counts[cond]["skipped_missing_ttft"],
            "skipped_outlier": counts[cond]["skipped_outlier"],
            "ttft_ms_mean": mean(xs),
            "ttft_ms_median": median(xs),
            "ttft_ms_p05": percentile(xs, 0.05),
            "ttft_ms_p25": percentile(xs, 0.25),
            "ttft_ms_p75": percentile(xs, 0.75),
            "ttft_ms_p95": percentile(xs, 0.95),
            "ttft_ms_min": min(xs),
            "ttft_ms_max": max(xs),
        })

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    cols = [
        "condition", "n", "total", "skipped_error", "skipped_missing_ttft", "skipped_outlier",
        "ttft_ms_mean", "ttft_ms_median",
        "ttft_ms_p05", "ttft_ms_p25", "ttft_ms_p75", "ttft_ms_p95",
        "ttft_ms_min", "ttft_ms_max"
    ]

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r[c]) for c in cols) + "\n")

    labels = [r["condition"] for r in rows]
    data = [groups[r["condition"]] for r in rows]

    out_png = Path(args.out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(9, 5))
    plt.boxplot(data, tick_labels=labels, showmeans=True)
    plt.ylabel("TTFT (ms)")
    plt.xlabel("Prefix overlap condition")
    plt.title("T11 real vLLM prefix-overlap TTFT")
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# T11 Real vLLM Prefix-Overlap V2")
    lines.append("")
    lines.append("Status: completed controlled low-memory RTX 4060 vLLM experiment.")
    lines.append("")
    lines.append("## Data quality")
    lines.append("")
    lines.append(f"- total raw rows: {total_rows}")
    lines.append(f"- skipped rows with request error: {skipped_error}")
    lines.append(f"- skipped rows with missing TTFT: {skipped_missing_ttft}")
    lines.append(f"- skipped TTFT outliers above {args.max_ttft_ms:.0f} ms: {skipped_outlier}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| condition | used n | raw n | mean TTFT ms | median TTFT ms | p95 TTFT ms | skipped error | skipped outlier |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r['condition']} | {r['n']} | {r['total']} | "
            f"{r['ttft_ms_mean']:.2f} | {r['ttft_ms_median']:.2f} | {r['ttft_ms_p95']:.2f} | "
            f"{r['skipped_error']} | {r['skipped_outlier']} |"
        )

    if "overlap_0" in groups and "overlap_100" in groups:
        base = mean(groups["overlap_0"])
        full = mean(groups["overlap_100"])
        delta = full - base
        pct = delta / base * 100.0 if base else float("nan")
        lines.append("")
        lines.append("## Key comparison")
        lines.append("")
        lines.append(f"- overlap_0 mean TTFT: {base:.2f} ms")
        lines.append(f"- overlap_100 mean TTFT: {full:.2f} ms")
        lines.append(f"- delta: {delta:.2f} ms ({pct:.2f}%)")
        if full < base:
            lines.append("- Interpretation: higher prefix overlap reduces TTFT in this low-memory smoke setting.")
        else:
            lines.append("- Interpretation: this run does not show a lower mean TTFT for full overlap; inspect request ordering, cache warmup, and outliers.")

    lines.append("")
    lines.append("## Caveat")
    lines.append("")
    lines.append("This is a low-memory RTX 4060 smoke experiment. Timeout/error rows and large timeout-induced TTFT outliers are explicitly excluded from the clean summary and reported above.")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({r["condition"]: r for r in rows}, indent=2))
    print(f"Wrote CSV to {out_csv}")
    print(f"Wrote plot to {out_png}")
    print(f"Wrote note to {out_md}")

if __name__ == "__main__":
    main()

