#!/usr/bin/env python3
"""Manual, redacted one-query GitHub API canary; never used by CI or pull requests."""

from __future__ import annotations

import os

import requests

QUERY = "repo:cesaremcasa/OSS-Sentinel is:issue"
URL = "https://api.github.com/search/issues"


def main() -> int:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(
            URL,
            headers=headers,
            params={"q": QUERY, "per_page": 1, "page": 1},
            timeout=5.0,
        )
        status = response.status_code
        rate_headers = {
            key: response.headers.get(key)
            for key in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset")
        }
        count = 0
        if status == 200:
            payload = response.json()
            count = len(payload.get("items", [])) if isinstance(payload, dict) else 0
        print(f"status={status} count={count} rate_headers={rate_headers}")
        return 0 if status == 200 else 1
    except (requests.RequestException, ValueError, TypeError):
        print("status=error count=0 rate_headers={}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
