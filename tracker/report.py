#!/usr/bin/env python3
"""
Turn runs.jsonl from track.py into Grok visibility numbers.

    python tracker/report.py examples/sample-runs.jsonl --config tracker/prompts.example.json
    python tracker/report.py runs.jsonl --config my.json --by prompt
    python tracker/report.py runs.jsonl --config my.json --by domains --format csv

Views:
  brand    mention rate, citation rate and share of voice for you and each competitor
  prompt   your mention rate per prompt, its day to day swing, and how much of
           Grok's sourcing for that prompt came from X instead of the open web
  domains  the hosts Grok cited most, split into X and web
  day      your mention rate per calendar day

"Swing" is the population standard deviation of the daily mention rate in
percentage points. Grok can pull live X posts into an answer, so a prompt
with a high swing is one where a single thread can move you in or out.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import pstdev

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse import cites_domain, host, mentioned, source_kind  # noqa: E402


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def brands_from(config: dict) -> list[dict]:
    """Your brand first, then competitors. Each has names[] and domains[]."""
    return [config["brand"], *config.get("competitors", [])]


def pct(n: int, d: int) -> float:
    return round(100 * n / d, 1) if d else 0.0


def by_brand(rows: list[dict], brands: list[dict]) -> list[dict]:
    mentions = {b["name"]: 0 for b in brands}
    cited = {b["name"]: 0 for b in brands}
    for r in rows:
        for b in brands:
            mentions[b["name"]] += mentioned(r["text"], b["names"])
            cited[b["name"]] += cites_domain(r["citations"], b["domains"])
    total = sum(mentions.values())
    return [
        {
            "brand": b["name"],
            "answers": len(rows),
            "mention_rate": pct(mentions[b["name"]], len(rows)),
            "citation_rate": pct(cited[b["name"]], len(rows)),
            "share_of_voice": pct(mentions[b["name"]], total),
        }
        for b in brands
    ]


def by_prompt(rows: list[dict], brand: dict) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["prompt_id"]].append(r)
    out = []
    for pid, rs in groups.items():
        days: dict[str, list[int]] = defaultdict(list)
        kinds = Counter()
        for r in rs:
            days[r["ts"][:10]].append(mentioned(r["text"], brand["names"]))
            kinds.update(source_kind(u) for u in r["citations"])
        daily = [100 * sum(v) / len(v) for v in days.values()]
        out.append(
            {
                "prompt_id": pid,
                "answers": len(rs),
                "mention_rate": pct(sum(sum(v) for v in days.values()), len(rs)),
                "swing_pp": round(pstdev(daily), 1) if len(daily) > 1 else 0.0,
                "x_source_share": pct(kinds["x"], sum(kinds.values())),
            }
        )
    return sorted(out, key=lambda r: -r["swing_pp"])


def by_domain(rows: list[dict], top: int = 15) -> list[dict]:
    counts = Counter(h for r in rows for h in {host(u) for u in r["citations"]})
    kind = {host(u): source_kind(u) for r in rows for u in r["citations"]}
    return [
        {"domain": d, "kind": kind[d], "answers_citing": n, "share_of_answers": pct(n, len(rows))}
        for d, n in counts.most_common(top)
    ]


def by_day(rows: list[dict], brand: dict) -> list[dict]:
    days: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        days[r["ts"][:10]].append(mentioned(r["text"], brand["names"]))
    return [
        {"day": d, "answers": len(v), "mention_rate": pct(sum(v), len(v))}
        for d, v in sorted(days.items())
    ]


def render(table: list[dict], fmt: str) -> str:
    if not table:
        return "No rows."
    cols = list(table[0])
    if fmt == "csv":
        buf = []
        w = csv.DictWriter(_Sink(buf), fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(table)
        return "".join(buf).rstrip()
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in table]
    return "\n".join(lines)


class _Sink:
    def __init__(self, buf: list[str]):
        self.buf = buf

    def write(self, s: str) -> None:
        self.buf.append(s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", type=Path)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--by", choices=["brand", "prompt", "domains", "day"], default="brand")
    ap.add_argument("--format", choices=["md", "csv"], default="md")
    args = ap.parse_args()

    rows = load_rows(args.runs)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    brands = brands_from(config)

    table = {
        "brand": lambda: by_brand(rows, brands),
        "prompt": lambda: by_prompt(rows, brands[0]),
        "domains": lambda: by_domain(rows),
        "day": lambda: by_day(rows, brands[0]),
    }[args.by]()
    print(render(table, args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
