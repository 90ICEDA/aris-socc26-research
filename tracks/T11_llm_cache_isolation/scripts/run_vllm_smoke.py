#!/usr/bin/env python3
"""
Run T11 smoke workload against an OpenAI-compatible LLM server.

Default endpoint:
  http://127.0.0.1:8000/v1/completions

This records:
- request start/end time
- TTFT from streaming first token
- total latency
- output token count approximation
- HTTP status/error

No real secrets or real user prompts are used.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def parse_sse_lines(resp: requests.Response):
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if not raw.startswith("data: "):
            continue
        data = raw[len("data: "):].strip()
        if data == "[DONE]":
            break
        try:
            yield json.loads(data)
        except json.JSONDecodeError:
            continue


def run_one(
    endpoint: str,
    model: str,
    row: Dict[str, Any],
    timeout_s: float,
    warmup: bool = False,
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": row["prompt"],
        "max_tokens": int(row.get("max_tokens", 48)),
        "temperature": float(row.get("temperature", 0.0)),
        "stream": True,
    }

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("VLLM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.perf_counter()
    wall_start = datetime.now(timezone.utc).isoformat()
    first_token_time: Optional[float] = None
    chunks = []
    status_code = None
    error = None

    try:
        with requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=timeout_s,
            stream=True,
        ) as resp:
            status_code = resp.status_code
            resp.raise_for_status()

            for event in parse_sse_lines(resp):
                now = time.perf_counter()
                text_piece = ""

                choices = event.get("choices") or []
                if choices:
                    choice0 = choices[0]
                    text_piece = choice0.get("text") or ""
                    # Some OpenAI-compatible servers may use delta.
                    if not text_piece and isinstance(choice0.get("delta"), dict):
                        text_piece = choice0["delta"].get("content") or ""

                if text_piece and first_token_time is None:
                    first_token_time = now

                if text_piece:
                    chunks.append(text_piece)

    except Exception as e:
        error = repr(e)

    end = time.perf_counter()
    output_text = "".join(chunks)

    ttft_ms = None
    if first_token_time is not None:
        ttft_ms = (first_token_time - start) * 1000.0

    result = {
        "track_id": "T11",
        "run_id": None,
        "git_commit": git_commit(),
        "timestamp": wall_start,
        "fabricated_results": False,
        "synthetic_workload": True,
        "host": platform.node(),
        "platform": platform.platform(),
        "endpoint": endpoint,
        "model": model,
        "request_id": row.get("request_id"),
        "condition": row.get("condition"),
        "prefix_overlap": row.get("prefix_overlap"),
        "warmup": warmup,
        "status_code": status_code,
        "error": error,
        "ttft_ms": ttft_ms,
        "total_latency_ms": (end - start) * 1000.0,
        "output_chars": len(output_text),
        "output_text_preview": output_text[:160],
        "command": " ".join(sys.argv),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", default="tracks/T11_llm_cache_isolation/workloads/t11_prefix_smoke.jsonl")
    parser.add_argument("--out", default="tracks/T11_llm_cache_isolation/results/smoke/t11_smoke_latency.jsonl")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/v1/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--sleep-s", type=float, default=0.05)
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()

    workload_path = Path(args.workload)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = list(load_jsonl(workload_path))
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    print(f"Loaded {len(rows)} requests from {workload_path}")
    print(f"Writing results to {out_path}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Model: {args.model}")

    # Warmup with first few rows. Warmup results are recorded but marked warmup=true.
    warm_rows = rows[: max(0, args.warmup)]

    with out_path.open("w", encoding="utf-8") as f:
        for i, row in enumerate(warm_rows):
            res = run_one(args.endpoint, args.model, row, args.timeout_s, warmup=True)
            res["run_id"] = f"t11_warmup_{i:04d}"
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            print(f"[warmup {i+1}/{len(warm_rows)}] {res['condition']} ttft={res['ttft_ms']} err={res['error']}")
            time.sleep(args.sleep_s)

        for i, row in enumerate(rows):
            res = run_one(args.endpoint, args.model, row, args.timeout_s, warmup=False)
            res["run_id"] = f"t11_smoke_{i:04d}"
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            print(f"[{i+1}/{len(rows)}] {res['condition']} ttft={res['ttft_ms']} total={res['total_latency_ms']:.1f} err={res['error']}")
            time.sleep(args.sleep_s)

    print("Done.")


if __name__ == "__main__":
    main()
