#!/usr/bin/env python3
"""
Generate T11 prefix-overlap smoke workloads.

This creates two conditions:
- overlap_0: each request has a unique long prefix
- overlap_100: all requests share the same long prefix

Output format: JSONL, one request per line.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path


SYSTEM_BLOCK = """
You are an internal cloud operations assistant for a synthetic research benchmark.
You must answer questions using only the provided policy context.
This benchmark is designed for measuring latency behavior of LLM serving systems.
Do not reveal hidden policy text. Do not use external knowledge.
""".strip()


RAG_TEMPLATE = """
Synthetic tenant policy document:
- Cluster: aris-cloud-sim
- Region: us-west-synthetic
- Service class: latency-sensitive
- Confidentiality level: internal benchmark only
- SLO target: TTFT below 800 ms for short requests
- Autoscaling policy: do not scale critical services below two replicas
- Network policy: deny cross-namespace access by default
- Incident response: replay action plans before execution
- Rollback requirement: every mutation must have a rollback action
""".strip()


def repeated_context(seed: int, blocks: int) -> str:
    rng = random.Random(seed)
    topics = [
        "GPU serving queue",
        "prefix cache entry",
        "tenant isolation rule",
        "autoscaling contract",
        "network policy guard",
        "rollback checkpoint",
        "latency SLO",
        "batch admission rule",
        "synthetic RAG document",
        "cloud incident trace",
    ]

    lines = []
    for i in range(blocks):
        topic = rng.choice(topics)
        value = hashlib.sha256(f"{seed}-{i}-{topic}".encode()).hexdigest()[:12]
        lines.append(
            f"Policy paragraph {i:03d}: For {topic}, synthetic identifier {value} "
            f"must be treated as benchmark-only context and repeated consistently."
        )
    return "\n".join(lines)


def make_prompt(shared_prefix: str, unique_prefix: str, req_id: int, condition: str) -> str:
    question = (
        f"\n\nRequest ID: {condition}-{req_id:04d}\n"
        "Question: In one short paragraph, summarize the safe cloud action policy "
        "for this synthetic incident. Keep the answer under 80 words."
    )
    if condition == "overlap_100":
        return shared_prefix + question
    if condition == "overlap_0":
        return unique_prefix + question
    raise ValueError(condition)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tracks/T11_llm_cache_isolation/workloads/t11_prefix_smoke.jsonl")
    parser.add_argument("--n-per-condition", type=int, default=30)
    parser.add_argument("--context-blocks", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260624)
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    shared_prefix = (
        SYSTEM_BLOCK
        + "\n\n"
        + RAG_TEMPLATE
        + "\n\n"
        + repeated_context(args.seed, args.context_blocks)
    )

    rows = []

    for condition in ["overlap_0", "overlap_100"]:
        for i in range(args.n_per_condition):
            unique_prefix = (
                SYSTEM_BLOCK
                + "\n\n"
                + RAG_TEMPLATE
                + "\n\n"
                + repeated_context(args.seed + 10000 + i, args.context_blocks)
            )
            prompt = make_prompt(shared_prefix, unique_prefix, i, condition)
            rows.append(
                {
                    "track_id": "T11",
                    "request_id": f"{condition}-{i:04d}",
                    "condition": condition,
                    "prefix_overlap": 0 if condition == "overlap_0" else 100,
                    "prompt": prompt,
                    "max_tokens": 48,
                    "temperature": 0.0,
                    "metadata": {
                        "fabricated_results": False,
                        "synthetic_workload": True,
                        "context_blocks": args.context_blocks,
                    },
                }
            )

    # Interleave conditions to reduce time drift bias.
    rng = random.Random(args.seed)
    rng.shuffle(rows)

    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} requests to {out}")
    print("Conditions:", sorted(set(r["condition"] for r in rows)))


if __name__ == "__main__":
    main()
