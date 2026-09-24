#!/usr/bin/env python3
"""ARGUS — pull the US trade.gov Consolidated Screening List and extract
entries matching known spyware vendors / corporate entities.

Source: https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.json
Free, no key, updated daily. US government work (public domain).

Writes ../data/screening_list.json with match metadata + matched entries.
Exit 0 on success, non-zero on fetch/parse failure.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CSL_URL = "https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.json"

# Extra match terms beyond vendor names/aliases (corporate shells, list quirks).
EXTRA_TERMS = [
    "Computer Security Initiative Consultancy",
    "Saito", "Cytrox", "Intellexa", "Candiru", "NSO Group",
    "Q Cyber", "Positive Technologies", "FinFisher", "Gamma Group",
    "Hacking Team", "RCS Lab", "Cy4Gate", "Cognyte", "Trovicor",
    "Paragon Solutions", "QuaDream", "Nexa Technologies", "Amesys",
    "WiSpear", "Passitora",
]


def load_terms() -> list[str]:
    terms: set[str] = set(EXTRA_TERMS)
    for fname in ("vendors.json", "corporate_entities.json"):
        path = os.path.join(DATA, fname)
        if not os.path.exists(path):
            continue
        for row in json.load(open(path)):
            terms.add(row["name"])
            for a in row.get("aliases", []) or []:
                terms.add(a)
    # Drop terms too short to match safely.
    return sorted(t for t in terms if len(t.strip()) >= 3)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


# CSL entries whose names collide with vendor terms but are unrelated
# (verified by inspection, 2026-09-24).
FALSE_POSITIVE_NAMES = {
    "lazarus group",  # OFAC alias "WHOIS HACKING TEAM" is not the Italian vendor
}


def term_hits(hay: str, terms: list[str]) -> list[str]:
    """Word-boundary matching so 'Appin' doesn't hit 'HAPPINESS'."""
    hits = []
    for t in terms:
        tn = norm(t)
        if not tn:
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(tn) + r"(?![a-z0-9])", hay):
            hits.append(t)
    return hits


def main() -> None:
    terms = load_terms()
    print(f"matching {len(terms)} terms against the Consolidated Screening List...")

    req = urllib.request.Request(CSL_URL, headers={"User-Agent": "argus-osint/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.load(resp)

    results = payload.get("results", [])
    scanned_at = payload.get("search_performed_at")
    matched = []
    for entry in results:
        if norm(entry.get("name")) in FALSE_POSITIVE_NAMES:
            continue
        hay = " ".join([
            norm(entry.get("name")),
            *[norm(a) for a in entry.get("alt_names", []) or []],
        ])
        hits = term_hits(hay, terms)
        if not hits:
            continue
        matched.append({
            "csl_id": entry.get("id"),
            "entity_number": entry.get("entity_number"),
            "name": entry.get("name"),
            "alt_names": entry.get("alt_names") or [],
            "type": entry.get("type"),
            "source": entry.get("source"),
            "programs": entry.get("programs") or [],
            "remarks": entry.get("remarks"),
            "addresses": [
                {k: a.get(k) for k in ("address", "city", "state", "postal_code", "country")}
                for a in entry.get("addresses", []) or []
            ],
            "source_information_url": entry.get("source_information_url"),
            "source_list_url": entry.get("source_list_url"),
            "matched_terms": sorted(set(hits)),
        })

    out = {
        "source": "US Consolidated Screening List (trade.gov)",
        "source_url": "https://www.trade.gov/consolidated-screening-list",
        "data_url": CSL_URL,
        "retrieved_date": datetime.date.today().isoformat(),
        "csl_search_performed_at": scanned_at,
        "entries_scanned": len(results),
        "match_terms": terms,
        "matches": len(matched),
        "entries": matched,
    }
    dest = os.path.join(DATA, "screening_list.json")
    with open(dest, "w") as f:
        json.dump(out, f, indent=2, separators=(",", ": "))
        f.write("\n")
    print(f"scanned {len(results)} entries, {len(matched)} matches -> {dest}")
    for m in matched:
        print(f"  - {m['name']} [{m['source']}] terms={m['matched_terms']}")


if __name__ == "__main__":
    sys.exit(main())
