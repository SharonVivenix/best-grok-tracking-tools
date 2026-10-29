#!/usr/bin/env python3
"""
Run a prompt set against Grok through the xAI Responses API and log what came back.

    export XAI_API_KEY=...
    python tracker/track.py --config tracker/prompts.example.json --runs 3
    python tracker/track.py --config tracker/prompts.example.json --dry-run

Each prompt is sent with the server side web_search and x_search tools enabled,
the same two retrieval paths the consumer Grok app uses. One JSON line per
answer is appended to --out, so repeated daily runs build a history that
tracker/report.py can aggregate. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse import all_citations, inline_urls, output_text  # noqa: E402

API_URL = "https://api.x.ai/v1/responses"
RETRY_STATUS = {429, 500, 502, 503, 504}


def build_payload(prompt: str, model: str, web: bool = True, x: bool = True) -> dict:
    tools = ([{"type": "web_search"}] if web else []) + ([{"type": "x_search"}] if x else [])
    payload = {"model": model, "input": [{"role": "user", "content": prompt}]}
    if tools:
        payload["tools"] = tools
    return payload


def call(payload: dict, key: str, retries: int = 4, timeout: int = 180) -> dict:
    body = json.dumps(payload).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUS or attempt == retries:
                raise SystemExit(f"xAI API error {e.code}: {e.read().decode(errors='replace')[:300]}")
            time.sleep(2 ** attempt)
    raise SystemExit("unreachable")


def to_row(resp: dict, prompt: dict, run: int, model: str) -> dict:
    text = output_text(resp)
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt_id": prompt["id"],
        "prompt": prompt["text"],
        "run": run,
        "model": resp.get("model", model),
        "text": text,
        "citations": all_citations(resp),
        "inline": inline_urls(text),
        "usage": resp.get("usage"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("runs.jsonl"))
    ap.add_argument("--runs", type=int, default=1, help="repeats per prompt, Grok answers vary per call")
    ap.add_argument("--model", default="grok-4.7")
    ap.add_argument("--no-web-search", action="store_true")
    ap.add_argument("--no-x-search", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between calls")
    ap.add_argument("--dry-run", action="store_true", help="print payloads, call nothing")
    args = ap.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    prompts = config["prompts"]

    if args.dry_run:
        for p in prompts:
            print(json.dumps(build_payload(p["text"], args.model, not args.no_web_search, not args.no_x_search)))
        print(f"{len(prompts)} prompts x {args.runs} runs = {len(prompts) * args.runs} calls", file=sys.stderr)
        return 0

    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise SystemExit("Set XAI_API_KEY first, or use --dry-run.")

    with args.out.open("a", encoding="utf-8") as fh:
        for p in prompts:
            payload = build_payload(p["text"], args.model, not args.no_web_search, not args.no_x_search)
            for run in range(1, args.runs + 1):
                row = to_row(call(payload, key), p, run, args.model)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"{p['id']} run {run}: {len(row['citations'])} sources, {len(row['inline'])} cited inline")
                time.sleep(args.sleep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
