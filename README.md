# hrackarium.cz

Static price comparison of toys from Czech e-shops (affiliate feeds from CJ, eHub, Dognet).

- `scripts/fetch.py` — download offers from the networks into `data/raw/` (not committed)
- `scripts/taxonomy.py` — toy category tree, classifier, LEGO series, characters, age parsing
- `scripts/catalog.py` — match offers across shops (EAN, set numbers), stable slugs, price history
- `scripts/build.py` + `render.py` + `texts.py` — plain-Python static site generator → `dist/`
- `scripts/deploy.py` — Cloudflare Workers **static assets only** (no Worker script, nothing billed per request);
  product pages are split into shard Workers when one Worker would exceed 100 000 files
- `.github/workflows/build.yml` — daily build in GitHub Actions

## Secrets

This repository is public. It contains code only: no API keys, no feed URLs, no catalogue data.
Keys live in GitHub Actions secrets; the build state is stored as an **encrypted** release asset (`scripts/state.sh`).
`scripts/verify_no_secrets.py` and gitleaks run on every build and fail it if a secret value shows up in the repo or the output.
Affiliate IDs inside product links (CJ website id, eHub/Dognet tracking ids) are public by nature.

Python 3.11+, standard library only (Pillow was used once to prepare the images; it is not part of the build).
