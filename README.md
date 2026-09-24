# ARGUS — watching the watchers

An open, sourced database of the **commercial spyware / lawful-intercept industry**: vendors, products, corporate structures and rebrand chains, legal and regulatory actions, and US screening-list hits.

**Live site:** deployed on Vercel (see below)
**Tagline:** *Watching the watchers — an open, sourced database of the commercial spyware industry.*

## Data

| File | Rows | What |
|---|---|---|
| `data/vendors.json` | 25 | Vendors: name, aliases, HQ country, status, description, source_ids |
| `data/products.json` | 9 | Products: name, vendor, category, source_ids |
| `data/corporate_entities.json` | 14 | Subsidiaries, holding/intermediary firms, acquirers (the rebrand maze) |
| `data/legal_actions.json` | 4 | Entity List additions, sanctions, lawsuits — with docket citations |
| `data/sources.json` | 9 | Provenance spine: every claim resolves to a source row |
| `data/screening_list.json` | 14 matches | Live pull of the US Consolidated Screening List, matched against vendor names/aliases |

IDs are stable slugs (`vendor:nso-group`). Every row carries `source_ids`.

## Claim-strength system

`confirmed` / `forensically_attributed` / `reported` / `alleged` / `denied` — mandatory on customer links and incidents. Denials are first-class rows. See `methodology.html` on the site.

## Scripts

- `scripts/pull_csl.py` — pulls the trade.gov Consolidated Screening List (free, no key, daily) and word-boundary-matches 49 vendor/alias terms. Re-run weekly; diff the output for new `legal_actions` rows.
- `scripts/push_argus.py` — pushes this directory to GitHub (`argus` repo) via the Git Data API.
- `scripts/deploy_argus.py` — creates/updates the Vercel project and deploys to production.

## Hard rules (from SPEC.md)

- Zero fabricated data. No source → no row.
- Public data only. No bypassing access controls, logins, paywalls, CAPTCHAs.
- No interception tooling, no live IOCs, no leaked-database mirroring, no victim PII beyond published reporting.
- Dockets over headlines: legal outcomes quoted from primary records.

## Status: v0

Shipped: vendors, products, corporate entities, legal actions, sources, live screening-list pull, static site.
Next pass: incident and customer-link curation (Citizen Lab / Amnesty / Google TAG / Meta reports) — only with explicit sources and claim-strength labels.
