#!/usr/bin/env python3
"""
crawl.py — Internal Link Score calculator for draincleanfinder.com

Usage:
    python crawl.py --url http://localhost:8080
    python crawl.py --url http://localhost:8080 --output results/
    python crawl.py --url https://draincleanfinder.com --output results/ --live

Outputs:
    - ILS score (0-100) printed to terminal
    - Detailed JSON report saved to --output dir
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict, deque
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ── Config ─────────────────────────────────────────────────────────────────

MAX_PAGES        = 2000   # safety cap — increase for very large sites
CRAWL_DELAY      = 0.1    # seconds between requests (be polite on live)
MAX_DEPTH        = 8      # max crawl depth from homepage
NEARBY_CITIES    = 5      # expected number of nearby city links per city page
PAGERANK_ITERS   = 50     # power iteration steps
PAGERANK_DAMPING = 0.85


# ── Helpers ─────────────────────────────────────────────────────────────────

def normalise(url, base):
    """Resolve relative URLs and strip fragments/query strings."""
    parsed = urlparse(urljoin(base, url))
    return parsed._replace(fragment="", query="").geturl()


def is_internal(url, base_domain):
    return urlparse(url).netloc == base_domain


def classify(path):
    """
    Classify a URL path into site structure tier.
    Returns one of: homepage, national_hub, state_hub, city, other

    URL structure for draincleanfinder.com:
        /                              → homepage
        /drain-cleaning/               → national_hub
        /drain-cleaning/[state]/       → state_hub  e.g. /drain-cleaning/colorado/
        /drain-cleaning/[state]/[city] → city       e.g. /drain-cleaning/colorado/denver/
    """
    STATES = {
        "alabama","alaska","arizona","arkansas","california","colorado",
        "connecticut","delaware","florida","georgia","hawaii","idaho",
        "illinois","indiana","iowa","kansas","kentucky","louisiana",
        "maine","maryland","massachusetts","michigan","minnesota",
        "mississippi","missouri","montana","nebraska","nevada",
        "new-hampshire","new-jersey","new-mexico","new-york",
        "north-carolina","north-dakota","ohio","oklahoma","oregon",
        "pennsylvania","rhode-island","south-carolina","south-dakota",
        "tennessee","texas","utah","vermont","virginia","washington",
        "west-virginia","wisconsin","wyoming",
    }

    parts = [p for p in path.strip("/").split("/") if p]

    if not parts:
        return "homepage"
    if parts == ["drain-cleaning"]:
        return "national_hub"
    if len(parts) == 2 and parts[0] == "drain-cleaning" and parts[1] in STATES:
        return "state_hub"
    if len(parts) == 3 and parts[0] == "drain-cleaning" and parts[1] in STATES:
        return "city"
    return "other"


# ── Crawler ──────────────────────────────────────────────────────────────────

def crawl(base_url, max_pages=MAX_PAGES, delay=CRAWL_DELAY):
    """
    BFS crawl from base_url.
    Returns:
        pages       dict[url] = { 'depth': int, 'links_out': [url], 'type': str }
        adjacency   dict[url] = set(urls it links to)
    """
    base_domain = urlparse(base_url).netloc
    visited     = {}          # url → depth
    adjacency   = defaultdict(set)
    queue       = deque([(base_url, 0)])
    session     = requests.Session()
    session.headers.update({"User-Agent": "draincleanfinder-crawler/1.0 (internal audit)"})

    print(f"\n🕷  Crawling {base_url} ...")

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()

        if url in visited or depth > MAX_DEPTH:
            continue

        try:
            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            if "text/html" not in resp.headers.get("content-type", ""):
                continue
        except Exception as e:
            print(f"  ⚠  {url}: {e}")
            continue

        soup  = BeautifulSoup(resp.text, "html.parser")
        links = []

        for tag in soup.find_all("a", href=True):
            href = normalise(tag["href"], url)
            if is_internal(href, base_domain):
                links.append(href)
                adjacency[url].add(href)
                if href not in visited:
                    queue.append((href, depth + 1))

        path = urlparse(url).path
        visited[url] = {
            "depth":     depth,
            "links_out": links,
            "links_in":  0,   # filled in below
            "type":      classify(path),
            "path":      path,
        }

        if len(visited) % 50 == 0:
            print(f"  … {len(visited)} pages crawled")

        time.sleep(delay)

    # Count inbound links for each page
    for src, targets in adjacency.items():
        for tgt in targets:
            if tgt in visited:
                visited[tgt]["links_in"] = visited[tgt].get("links_in", 0) + 1

    print(f"  ✓ Done. {len(visited)} pages found.\n")
    return visited, dict(adjacency)


# ── Metrics ──────────────────────────────────────────────────────────────────

def score_crawl_depth(pages):
    """
    % of pages reachable within 3 clicks. Target 90%.
    Score: 0-40.
    """
    total   = len(pages)
    if total == 0:
        return 0, {}
    within3 = sum(1 for p in pages.values() if p["depth"] <= 3)
    pct     = within3 / total
    score   = round(pct * 40, 2)

    detail = {
        "total_pages":    total,
        "within_3_clicks": within3,
        "pct_within_3":   round(pct * 100, 1),
        "score":          score,
    }
    return score, detail


def score_orphan_rate(pages):
    """
    % of pages with zero inbound internal links. Target <5%.
    Score: 0-30.
    """
    total   = len(pages)
    if total == 0:
        return 0, {}
    orphans = [u for u, p in pages.items() if p.get("links_in", 0) == 0 and p["type"] != "homepage"]
    rate    = len(orphans) / total
    # Invert: 0% orphans = 30 points, 20%+ orphans = 0 points
    score   = max(0, round((1 - (rate / 0.20)) * 30, 2))

    detail = {
        "total_pages":   total,
        "orphan_count":  len(orphans),
        "orphan_rate":   round(rate * 100, 1),
        "sample_orphans": orphans[:10],
        "score":         score,
    }
    return score, detail


def compute_pagerank(pages, adjacency, iters=PAGERANK_ITERS, d=PAGERANK_DAMPING):
    """Iterative PageRank computation."""
    urls = list(pages.keys())
    n    = len(urls)
    if n == 0:
        return {}

    pr = {u: 1.0 / n for u in urls}

    for _ in range(iters):
        new_pr = {}
        for u in urls:
            inbound_sum = 0.0
            for src, targets in adjacency.items():
                if u in targets and len(targets) > 0:
                    inbound_sum += pr.get(src, 0) / len(targets)
            new_pr[u] = (1 - d) / n + d * inbound_sum
        pr = new_pr

    return pr


def gini(values):
    """Gini coefficient. 0 = perfectly equal, 1 = perfectly unequal."""
    if not values:
        return 0
    vals   = sorted(values)
    n      = len(vals)
    total  = sum(vals)
    if total == 0:
        return 0
    cumsum = 0
    for i, v in enumerate(vals):
        cumsum += v
    # Standard formula
    numer = 2 * sum((i + 1) * v for i, v in enumerate(vals))
    denom = n * total
    return round((numer / denom) - (n + 1) / n, 4)


def score_pagerank_distribution(pages, adjacency):
    """
    Lower Gini = more even distribution = better.
    Score: 0-20.
    """
    pr     = compute_pagerank(pages, adjacency)
    g      = gini(list(pr.values()))
    # Gini of 0.0 = 20 pts, Gini of 1.0 = 0 pts
    score  = round((1 - g) * 20, 2)

    top10  = sorted(pr.items(), key=lambda x: x[1], reverse=True)[:10]

    detail = {
        "gini_coefficient": g,
        "top_10_pages":     [(u, round(v, 6)) for u, v in top10],
        "score":            score,
    }
    return score, detail


def score_hub_connectivity(pages, adjacency):
    """
    Check state hubs link to all their city pages,
    and city pages link back to their state hub.
    Score: 0-10.
    """
    state_hubs  = {u: p for u, p in pages.items() if p["type"] == "state_hub"}
    city_pages  = {u: p for u, p in pages.items() if p["type"] == "city"}

    if not state_hubs or not city_pages:
        return 5, {"note": "Not enough state/city pages found to score hub connectivity."}

    # For each city page, does its state hub exist and link to it?
    city_has_hub_backlink   = 0
    hub_links_to_city       = 0
    total_checks            = 0

    for city_url, city_data in city_pages.items():
        parts     = [p for p in city_data["path"].strip("/").split("/") if p]
        # Expect: ["drain-cleaning", state, city]
        if len(parts) < 3 or parts[0] != "drain-cleaning":
            continue
        state     = parts[1]
        hub_url   = None

        # Find the state hub URL — matches /drain-cleaning/[state]
        for hu in state_hubs:
            hu_path = urlparse(hu).path.strip("/")
            if hu_path == f"drain-cleaning/{state}":
                hub_url = hu
                break

        if not hub_url:
            continue

        total_checks += 1

        # Does city page link back to hub?
        if hub_url in adjacency.get(city_url, set()):
            city_has_hub_backlink += 1

        # Does hub link to city?
        if city_url in adjacency.get(hub_url, set()):
            hub_links_to_city += 1

    if total_checks == 0:
        return 5, {"note": "Could not match city pages to state hubs."}

    hub_to_city_pct   = hub_links_to_city / total_checks
    city_to_hub_pct   = city_has_hub_backlink / total_checks
    combined          = (hub_to_city_pct + city_to_hub_pct) / 2
    score             = round(combined * 10, 2)

    detail = {
        "total_city_pages_checked": total_checks,
        "hub_links_to_city_pct":    round(hub_to_city_pct * 100, 1),
        "city_links_to_hub_pct":    round(city_to_hub_pct * 100, 1),
        "score":                    score,
    }
    return score, detail


# ── Main ─────────────────────────────────────────────────────────────────────

def run(base_url, output_dir=None, live=False):
    delay = 0.5 if live else CRAWL_DELAY

    pages, adjacency = crawl(base_url, delay=delay)

    s1, d1 = score_crawl_depth(pages)
    s2, d2 = score_orphan_rate(pages)
    s3, d3 = score_pagerank_distribution(pages, adjacency)
    s4, d4 = score_hub_connectivity(pages, adjacency)

    total = round(s1 + s2 + s3 + s4, 2)

    report = {
        "url":        base_url,
        "timestamp":  datetime.utcnow().isoformat(),
        "ILS":        total,
        "breakdown": {
            "crawl_depth":           {"score": s1, "max": 40, "detail": d1},
            "orphan_rate":           {"score": s2, "max": 30, "detail": d2},
            "pagerank_distribution": {"score": s3, "max": 20, "detail": d3},
            "hub_connectivity":      {"score": s4, "max": 10, "detail": d4},
        },
        "page_count": len(pages),
        "page_types": {t: sum(1 for p in pages.values() if p["type"] == t)
                       for t in ["homepage","national_hub","state_hub","city","other"]},
    }

    # Terminal output
    print("=" * 50)
    print(f"  INTERNAL LINK SCORE (ILS): {total} / 100")
    print("=" * 50)
    print(f"  Crawl depth score:      {s1:5.1f} / 40")
    print(f"  Orphan rate score:      {s2:5.1f} / 30")
    print(f"  PageRank distribution:  {s3:5.1f} / 20")
    print(f"  Hub connectivity:       {s4:5.1f} / 10")
    print("-" * 50)
    print(f"  Pages crawled: {len(pages)}")
    print(f"  Page types:    {report['page_types']}")

    if d2.get("orphan_count"):
        print(f"\n  ⚠  {d2['orphan_count']} orphan pages ({d2['orphan_rate']}%)")
        if d2.get("sample_orphans"):
            for u in d2["sample_orphans"]:
                print(f"     - {u}")

    print()

    # Save report
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        fname = os.path.join(output_dir, "latest.json")
        with open(fname, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  📄 Report saved to {fname}")

        # Also save a timestamped copy
        ts    = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        tname = os.path.join(output_dir, f"run_{ts}.json")
        with open(tname, "w") as f:
            json.dump(report, f, indent=2)

    return report


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Internal Link Score crawler")
    parser.add_argument("--url",    required=True, help="Base URL to crawl (e.g. http://localhost:8080)")
    parser.add_argument("--output", default=None,  help="Directory to save JSON reports")
    parser.add_argument("--live",   action="store_true", help="Use polite delay for live site crawling")
    args = parser.parse_args()

    run(args.url, output_dir=args.output, live=args.live)
