# Data provenance

The public baseline contains only repository-authored code, configuration, and
the synthetic fixture under `tests/fixtures/`. That fixture is dedicated to
the public domain under CC0 1.0 and is used for offline tests and examples.

Previously tracked CSV reports and PNG plots were generated from external
GitHub issue data and provider output without a redistribution record. They
were removed from the current HEAD; Git history was not rewritten. No claim
is made that historical blobs are suitable for redistribution.

Real runs require the operator to provide permitted GitHub API results in
`data/raw/` and to choose a provider explicitly. `OSS_SENTINEL_PROVIDER=fake`
is the safe deterministic default. `OSS_SENTINEL_PROVIDER=openai` requires
`OPENAI_API_KEY` and may send issue text to the configured provider.
