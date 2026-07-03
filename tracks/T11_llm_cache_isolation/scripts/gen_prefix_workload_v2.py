#!/usr/bin/env python3
import argparse
import hashlib
import json
import random
from pathlib import Path

POLICY_TOPICS = [
    "tenant isolation rule",
    "latency SLO",
    "prefix cache entry",
    "GPU serving queue",
    "batch admission rule",
    "rollback checkpoint",
    "network policy guard",
    "cloud incident trace",
]

def stable_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]

def make_para(topic: str, ident: str, idx: int) -> str:
    return (
        f"Policy paragraph {idx:03d}: For {topic}, synthetic identifier {ident} "
        f"must be treated as benchmark-only context and repeated consistently."
    )

def make_prompt(condition: str, req_id: str, shared_blocks, unique_blocks) -> str:
    context = "\n".join(shared_blocks + unique_blocks)
    return (
        "You are an internal benchmark assistant for a synthetic cloud incident.\n"
        "You must only use the policy text below.\n"
        "The incident is synthetic and contains no real customer data.\n"
        "Do not invent facts outside the policy context.\n\n"
        "Synthetic policy context:\n"
        f"{context}\n\n"
        f"Request ID: {req_id}\n"
        "Question: In one short paragraph, summarize the safe cloud action policy "
        "for this synthetic incident. Keep the answer under 80 words."
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-per-condition", type=int, default=30)
    ap.add_argument("--context-blocks", type=int, default=16)
    ap.add_argument("--levels", default="0,25,50,75,100")
    ap.add_argument("--seed", type=int, default=20260702)
    ap.add_argument("--max-tokens", type=int, default=48)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    levels = [int(x.strip()) for x in args.levels.split(",") if x.strip()]

    records = []

    for level in levels:
        condition = f"overlap_{level}"
        shared_n = round(args.context_blocks * level / 100)

        shared_blocks = []
        for i in range(shared_n):
            topic = POLICY_TOPICS[i % len(POLICY_TOPICS)]
            ident = stable_id(f"GLOBAL_SHARED_{level}_{i}")
            shared_blocks.append(make_para(topic, ident, i))

        for j in range(args.n_per_condition):
            unique_blocks = []
            for k in range(shared_n, args.context_blocks):
                topic = POLICY_TOPICS[(k + j) % len(POLICY_TOPICS)]
                ident = stable_id(f"{condition}_{j}_{k}_{args.seed}")
                unique_blocks.append(make_para(topic, ident, k))

            req_id = f"{condition}-{j:04d}"
            prompt = make_prompt(condition, req_id, shared_blocks, unique_blocks)

            records.append({
                "request_id": req_id,
                "id": req_id,
                "condition": condition,
                "overlap_pct": level,
                "shared_blocks": shared_n,
                "context_blocks": args.context_blocks,
                "prompt": prompt,
                "max_tokens": args.max_tokens,
            })

    rng.shuffle(records)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} requests to {out}")
    print(f"Levels: {levels}")
    print(f"n_per_condition: {args.n_per_condition}")
    print(f"context_blocks: {args.context_blocks}")

if __name__ == "__main__":
    main()
