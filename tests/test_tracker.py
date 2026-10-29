import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tracker"))

import parse  # noqa: E402
import report  # noqa: E402
from track import build_payload  # noqa: E402

RESPONSE = json.loads((ROOT / "examples" / "sample-response.json").read_text(encoding="utf-8"))
CONFIG = json.loads((ROOT / "tracker" / "prompts.example.json").read_text(encoding="utf-8"))


class ParseTests(unittest.TestCase):
    def test_output_text_skips_tool_calls(self):
        text = parse.output_text(RESPONSE)
        self.assertTrue(text.startswith("For Grok specifically"))

    def test_top_level_citations_win(self):
        self.assertEqual(len(parse.all_citations(RESPONSE)), 4)

    def test_annotation_fallback(self):
        resp = {k: v for k, v in RESPONSE.items() if k != "citations"}
        self.assertEqual(len(parse.all_citations(resp)), 3)

    def test_inline_urls(self):
        urls = parse.inline_urls(parse.output_text(RESPONSE))
        self.assertEqual(urls[1], "https://x.com/i/status/1981000000000000001")

    def test_source_kind(self):
        self.assertEqual(parse.source_kind("https://x.com/i/status/1"), "x")
        self.assertEqual(parse.source_kind("https://twitter.com/a"), "x")
        self.assertEqual(parse.source_kind("https://www.reddit.com/r/SEO"), "web")

    def test_domain_in_url_is_not_a_mention(self):
        text = "Try this.[[1]](https://contososignals.example/pricing)"
        self.assertFalse(parse.mentioned(text, ["contososignals"]))

    def test_whole_word_mention(self):
        self.assertTrue(parse.mentioned("I like Northwind.", ["Northwind"]))
        self.assertFalse(parse.mentioned("Northwinds of change", ["Northwind"]))

    def test_cites_domain_matches_www_and_subdomains(self):
        urls = ["https://www.contososignals.example/pricing", "https://blog.fabrikamrank.example/x"]
        self.assertTrue(parse.cites_domain(urls, ["contososignals.example"]))
        self.assertTrue(parse.cites_domain(urls, ["fabrikamrank.example"]))
        self.assertFalse(parse.cites_domain(urls, ["tailspinseo.example"]))


class ReportTests(unittest.TestCase):
    def rows(self):
        return [
            {"ts": "2026-10-01T00:00:00", "prompt_id": "p", "text": "Northwind Metrics wins.",
             "citations": ["https://x.com/i/status/1", "https://northwindmetrics.example/"]},
            {"ts": "2026-10-02T00:00:00", "prompt_id": "p", "text": "Fabrikam Rank wins.",
             "citations": ["https://g2.example/a", "https://g2.example/b"]},
        ]

    def test_brand_rates(self):
        table = {r["brand"]: r for r in report.by_brand(self.rows(), report.brands_from(CONFIG))}
        self.assertEqual(table["Northwind Metrics"]["mention_rate"], 50.0)
        self.assertEqual(table["Northwind Metrics"]["citation_rate"], 50.0)
        self.assertEqual(table["Northwind Metrics"]["share_of_voice"], 50.0)

    def test_swing_and_x_share(self):
        (row,) = report.by_prompt(self.rows(), CONFIG["brand"])
        self.assertEqual(row["swing_pp"], 50.0)
        self.assertEqual(row["x_source_share"], 25.0)

    def test_domain_counted_once_per_answer(self):
        table = {r["domain"]: r for r in report.by_domain(self.rows())}
        self.assertEqual(table["g2.example"]["answers_citing"], 1)

    def test_sample_file_loads(self):
        rows = report.load_rows(ROOT / "examples" / "sample-runs.jsonl")
        self.assertEqual(len(rows), 140)


class PayloadTests(unittest.TestCase):
    def test_both_search_tools_by_default(self):
        p = build_payload("q", "grok-4.7")
        self.assertEqual([t["type"] for t in p["tools"]], ["web_search", "x_search"])

    def test_no_tools_when_both_disabled(self):
        self.assertNotIn("tools", build_payload("q", "grok-4.7", web=False, x=False))


if __name__ == "__main__":
    unittest.main()
