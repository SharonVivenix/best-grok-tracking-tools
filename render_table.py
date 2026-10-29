#!/usr/bin/env python3
"""
Regenerate the comparison table in README.md from tools.yaml.

    python render_table.py               # print the table to stdout
    python render_table.py --write       # rewrite the block between the markers
    python render_table.py --check       # exit 1 if README and YAML disagree
    python render_table.py --budget 100  # tools whose Grok plan fits a budget

Grok is the engine vendors love to list and hate to include. The column that
matters here is the Grok premium: what a plan that really tracks Grok costs
minus the sticker price on the pricing page. It is computed, never typed, so
fixing one price in tools.yaml fixes the table too.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

START = "<!-- TABLE:START -->"
END = "<!-- TABLE:END -->"
HEADER = ["Tool", "Sticker price", "Cheapest plan with Grok", "Grok premium", "Refresh", "Trial", "Best for"]


def money(currency: str, value: float) -> str:
    return f"{currency}{value:,.2f}".replace(".00", "")


def premium(t: dict) -> str:
    if t.get("grok_price") is None:
        return "Not published"
    gap = t["grok_price"] - t["entry_price"]
    mark = "" if t.get("grok_confirmed", True) else " (confirm)"
    return ("None" if gap == 0 else "+" + money(t["currency"], gap)) + mark


def grok_cell(t: dict) -> str:
    if t.get("grok_price") is None:
        return t["grok_plan"]
    return f"{money(t['currency'], t['grok_price'])}/mo, {t['grok_plan']}"


def row(t: dict) -> list[str]:
    entry = "Free" if t["entry_price"] == 0 else f"{money(t['currency'], t['entry_price'])}/mo"
    return [
        f"[{t['name']}]({t['url']})",
        f"{entry}, {t['entry_plan']}",
        grok_cell(t),
        premium(t),
        t["refresh"],
        t["trial"],
        t["best_for"],
    ]


def build_table(tools: list[dict]) -> str:
    lines = ["| " + " | ".join(HEADER) + " |", "| " + " | ".join("---" for _ in HEADER) + " |"]
    lines += ["| " + " | ".join(row(t)) + " |" for t in tools]
    return "\n".join(lines)


def current_block(text: str) -> str:
    if START not in text or END not in text:
        raise SystemExit("README is missing the TABLE markers.")
    return text.split(START)[1].split(END)[0].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--budget", type=float, help="monthly budget, any currency")
    ap.add_argument("--data", type=Path, default=Path("tools.yaml"))
    ap.add_argument("--readme", type=Path, default=Path("README.md"))
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    tools = yaml.safe_load(args.data.read_text(encoding="utf-8"))["tools"]

    if args.budget is not None:
        fits = [t for t in tools if t.get("grok_price") is not None and t["grok_price"] <= args.budget]
        for t in sorted(fits, key=lambda t: t["grok_price"]):
            note = "" if t.get("grok_confirmed", True) else "  (Grok on this plan not named, confirm)"
            print(f"{money(t['currency'], t['grok_price']):>10}  {t['name']}{note}")
        if not fits:
            print("No tool publishes a Grok plan at or under that budget.")
        return 0

    table = build_table(tools)

    if args.check:
        text = args.readme.read_text(encoding="utf-8")
        if current_block(text) != table:
            print("README table is out of date. Run: python render_table.py --write", file=sys.stderr)
            return 1
        print(f"Table matches tools.yaml ({len(tools)} tools).")
        return 0

    if not args.write:
        print(table)
        return 0

    text = args.readme.read_text(encoding="utf-8")
    current_block(text)
    before, rest = text.split(START, 1)
    after = rest.split(END, 1)[1]
    args.readme.write_text(f"{before}{START}\n{table}\n{END}{after}", encoding="utf-8")
    print(f"Updated table in {args.readme} ({len(tools)} tools).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
