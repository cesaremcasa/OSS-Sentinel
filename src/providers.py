"""Classifier providers used by the enrichment stage.

The OpenAI dependency is intentionally imported only when the real provider is
selected and first used.  This keeps CLI help, tests, and offline processing
usable without a credential or an external service.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol


class IssueClassifier(Protocol):
    def classify_issue(self, title: str, body: str) -> dict[str, str]:
        """Return the normalized sentiment/category/urgency labels."""


class FakeProvider:
    """Deterministic local classifier for fixtures, tests, and offline runs."""

    def classify_issue(self, title: str, body: str) -> dict[str, str]:
        text = f"{title}\n{body}".lower()
        is_bug = any(word in text for word in ("bug", "error", "fail", "broken"))
        is_urgent = any(word in text for word in ("critical", "outage", "security"))
        is_feature = any(word in text for word in ("feature", "request", "add "))
        return {
            "sentiment": "negative" if is_bug else "neutral",
            "category": "bug" if is_bug else "feature_request" if is_feature else "other",
            "urgency": "high" if is_urgent else "medium" if is_bug else "low",
        }


class OpenAIProvider:
    """Lazy OpenAI JSON classifier; no SDK import or key check occurs at module import."""

    def __init__(self, model: str = "gpt-4o-mini", api_key_env: str = "OPENAI_API_KEY") -> None:
        self.model = model
        self.api_key_env = api_key_env
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"{self.api_key_env} is required for the OpenAI provider")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        return self._client

    def classify_issue(self, title: str, body: str) -> dict[str, str]:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify a GitHub issue. Return only JSON with keys "
                        "sentiment, category, urgency. sentiment is positive, neutral, or negative; "
                        "category is bug, feature_request, documentation, question, or other; "
                        "urgency is high, medium, or low."
                    ),
                },
                {"role": "user", "content": f"Title: {title}\nBody: {body[:2000]}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("provider response must be a JSON object")
        return {
            "sentiment": str(result.get("sentiment", "error")),
            "category": str(result.get("category", "unknown")),
            "urgency": str(result.get("urgency", "unknown")),
        }


def make_provider(name: str | None = None) -> IssueClassifier:
    """Build a provider, defaulting to the deterministic fake for safe local use."""

    selected = (name or os.getenv("OSS_SENTINEL_PROVIDER") or "fake").strip().lower()
    if selected == "fake":
        return FakeProvider()
    if selected in {"openai", "real"}:
        return OpenAIProvider()
    raise ValueError(f"unsupported provider: {selected}")
