"""
Pure helpers for reading xAI Responses API output. No network, no third party deps.

Shapes follow the xAI docs (docs.x.ai/developers/tools/citations):
  * response["citations"]  every URL the agent touched while searching
  * output[].content[] of type "output_text" carries the answer text and
    "url_citation" annotations for the sources it actually cites
  * inline citations appear in the text as [[N]](url)
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

X_HOSTS = {"x.com", "twitter.com", "mobile.twitter.com"}
INLINE_CITATION = re.compile(r"\[\[(\d+)\]\]\((https?://[^)\s]+)\)")


def output_text(resp: dict) -> str:
    """Concatenate every output_text block from message items."""
    parts = []
    for item in resp.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") == "output_text":
                parts.append(block.get("text", ""))
    return "\n".join(parts)


def annotation_urls(resp: dict) -> list[str]:
    """URLs from url_citation annotations, in order, deduplicated."""
    seen: dict[str, None] = {}
    for item in resp.get("output", []):
        for block in item.get("content", []) if item.get("type") == "message" else []:
            for ann in block.get("annotations") or []:
                if ann.get("type") == "url_citation" and ann.get("url"):
                    seen.setdefault(ann["url"], None)
    return list(seen)


def all_citations(resp: dict) -> list[str]:
    """Prefer the top level citations list, fall back to annotations."""
    return list(dict.fromkeys(resp.get("citations") or annotation_urls(resp)))


def inline_urls(text: str) -> list[str]:
    """URLs the answer text links inline, the ones a reader actually sees."""
    return list(dict.fromkeys(url for _, url in INLINE_CITATION.findall(text)))


def strip_citations(text: str) -> str:
    """Drop [[N]](url) markers so a brand domain inside a URL is not a mention."""
    return INLINE_CITATION.sub("", text)


def host(url: str) -> str:
    h = urlparse(url).netloc.lower().split(":")[0]
    return h[4:] if h.startswith("www.") else h


def source_kind(url: str) -> str:
    """'x' for posts and profiles on X, 'web' for everything else."""
    h = host(url)
    return "x" if h in X_HOSTS or h.endswith(".x.com") else "web"


def mentioned(text: str, names: list[str]) -> bool:
    """Case insensitive whole word match on any name or alias."""
    clean = strip_citations(text)
    return any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", clean, re.IGNORECASE) for n in names)


def cites_domain(urls: list[str], domains: list[str]) -> bool:
    hosts = {host(u) for u in urls}
    return any(h == d or h.endswith("." + d) for h in hosts for d in domains)
