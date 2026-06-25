#!/usr/bin/env python3
"""
Create synthetic T11 dry-run latency results.

This is NOT a real vLLM experiment.
It only validates result format and analyzer pipeline.
"""

import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def main():
    out = Path("tracks/T11_llm_cache_isolation/results/smoke/t11_dryrun_latency.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(20260624)
    rows = []

    for condition, base in [("overlap_0", 620.0), ("overlap_100", 360.0)]:
        for i in range(30):
            jitter = rng.gauss(0, 25)
            ttft = max(1.0, base + jitter)
            rows.append({
                "track_id": "T11",
                "run_id": f"t11_dryrun_{condition}_{i:04d}",
                "git_commit": git_commit(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fabricated_results": False,
                "synthetic_dry_run": True,
                "real_vllm_experiment": False,
                "endpoint": "none",
                "model": "dry-run-format-check",
                "request_id": f"{condition}-{i:04d}",
                "condition": condition,
                "prefix_overlap": 0 if condition == "overlap_0" else 100,
                "warmup": False,
                "status_code": None,
                "error": None,
                "ttft_ms": ttft,
                "total_latency_ms": ttft + 120 + rng.random() * 30,
                "output_chars": 80,
                "output_text_preview": "dry run only",
                "command": "python tracks/T11_llm_cache_isolation/scripts/dryrun_results.py"
            })

    rng.shuffle(rows)

    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote dry-run results to {out}")
    print("WARNING: this is a dry-run format check, not a real vLLM experiment.")


if __name__ == "__main__":
    main()
