"""GitHub issue ingestion with bounded retries, pagination, and a query cache."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import requests
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"
GITHUB_SEARCH_URL = "https://api.github.com/search/issues"

load_dotenv(BASE_DIR / "config" / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class IngestionError(RuntimeError):
    """A safe, actionable ingestion failure without response-body secrets."""


def _sleep_backoff(delay: float) -> None:
    time.sleep(delay)


class IngestionEngine:
    def __init__(
        self,
        output_dir="data/raw",
        config_path=None,
        session: Any | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff: Callable[[float], None] | None = None,
        cache_dir=None,
        cache_ttl: float = 300.0,
        clock: Callable[[], float] | None = None,
    ):
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if cache_ttl < 0:
            raise ValueError("cache_ttl must be non-negative")

        self.output_dir = BASE_DIR / output_dir
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.config = self._load_config()
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff or _sleep_backoff
        self.cache_dir = Path(cache_dir) if cache_dir else self.output_dir / ".cache"
        self.cache_ttl = cache_ttl
        self.clock = clock or time.time

    def _load_config(self):
        """Read the YAML search configuration."""
        try:
            with open(self.config_path, "r") as config_file:
                return yaml.safe_load(config_file) or {}
        except FileNotFoundError:
            logger.error("Arquivo de configuração não encontrado em: %s", self.config_path)
            raise
        except yaml.YAMLError as error:
            logger.error("Erro ao ler YAML: %s", error)
            raise

    def _get_date_filter(self, days_back):
        """Generate the date string used by GitHub search."""
        date_limit = datetime.now() - timedelta(days=days_back)
        return date_limit.strftime("%Y-%m-%d")

    def _cache_path(self, query: str, sort: str, order: str, max_results: int) -> Path:
        cache_key = "\0".join((query, sort, order, str(max_results))).encode("utf-8")
        return self.cache_dir / f"{hashlib.sha256(cache_key).hexdigest()}.json"

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        if self.cache_ttl == 0 or not path.is_file():
            return None
        try:
            cached = json.loads(path.read_text())
            age = self.clock() - float(cached["cached_at"])
            if age < 0 or age > self.cache_ttl:
                return None
            payload = cached["payload"]
            return payload if isinstance(payload, dict) else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write_cache(self, path: Path, payload: dict[str, Any]) -> None:
        if self.cache_ttl == 0:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"cached_at": self.clock(), "payload": payload}))
        temporary.replace(path)

    @staticmethod
    def _is_rate_limited(response: Any) -> bool:
        headers = getattr(response, "headers", {}) or {}
        return getattr(response, "status_code", None) == 429 or (
            getattr(response, "status_code", None) == 403
            and str(headers.get("X-RateLimit-Remaining", "")) == "0"
        )

    def _retry_delay(self, attempt: int, response: Any | None = None) -> float:
        headers = getattr(response, "headers", {}) or {}
        retry_after = headers.get("Retry-After")
        try:
            return max(0.0, float(str(retry_after)))
        except (TypeError, ValueError):
            reset_at = headers.get("X-RateLimit-Reset")
            try:
                return max(0.0, float(str(reset_at)) - self.clock())
            except (TypeError, ValueError):
                return float(2**attempt)

    def _get_json(self, params: dict[str, Any]) -> dict[str, Any]:
        last_status: int | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    GITHUB_SEARCH_URL,
                    headers=self.headers,
                    params=params,
                    timeout=self.timeout,
                )
            except requests.RequestException:
                if attempt >= self.max_retries:
                    raise IngestionError(
                        f"GitHub request failed after {attempt + 1} attempts (network error)"
                    ) from None
                self.backoff(self._retry_delay(attempt))
                continue

            last_status = getattr(response, "status_code", None)
            retryable = self._is_rate_limited(response) or (
                isinstance(last_status, int) and 500 <= last_status <= 599
            )
            if last_status == 200:
                try:
                    payload = response.json()
                except (ValueError, TypeError) as error:
                    raise IngestionError("GitHub returned invalid JSON") from error
                if not isinstance(payload, dict):
                    raise IngestionError("GitHub returned an unexpected response shape")
                return payload

            if retryable and attempt < self.max_retries:
                self.backoff(self._retry_delay(attempt, response))
                continue
            status_text = str(last_status) if last_status is not None else "unknown status"
            if retryable:
                raise IngestionError(
                    f"GitHub request failed after {attempt + 1} attempts (HTTP {status_text})"
                )
            raise IngestionError(f"GitHub request rejected (HTTP {status_text})")

        raise IngestionError(f"GitHub request failed (HTTP {last_status or 'unknown status'})")

    def fetch_github_issues(
        self,
        query,
        sort="created",
        order="desc",
        per_page=100,
        max_results=None,
    ):
        """Fetch up to ``max_results`` issues, following search result pages."""
        limit = max_results if max_results is not None else per_page
        if limit <= 0:
            return {"total_count": 0, "items": []}
        page_size = min(max(1, per_page), 100, limit)
        cache_path = self._cache_path(query, sort, order, limit)
        cached = self._read_cache(cache_path)
        if cached is not None:
            logger.info("Cache hit for GitHub query")
            return cached

        logger.info("Buscando com query: %s", query)
        items: list[Any] = []
        page = 1
        total_count: int | None = None
        while len(items) < limit:
            payload = self._get_json(
                {
                    "q": query,
                    "sort": sort,
                    "order": order,
                    "per_page": page_size,
                    "page": page,
                }
            )
            page_items = payload.get("items", [])
            if not isinstance(page_items, list):
                raise IngestionError("GitHub returned an invalid items collection")
            items.extend(page_items[: limit - len(items)])
            if total_count is None and isinstance(payload.get("total_count"), int):
                total_count = payload["total_count"]
            if len(page_items) < page_size or not page_items:
                break
            page += 1

        result = {"total_count": total_count if total_count is not None else len(items), "items": items}
        self._write_cache(cache_path, result)
        return result

    def save_raw_data(self, data, source_name):
        """Save raw JSON with the target repository name."""
        if not data:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"ingest_{source_name}_{timestamp}.json"
        with open(filepath, "w") as output_file:
            json.dump(data, output_file, indent=4)
        logger.info("Salvo: %s", filepath)

    def run(self):
        """Run ingestion for all configured targets."""
        targets = self.config.get("github", {}).get("targets", [])
        params = self.config.get("parameters", {})
        days_back = params.get("days_back", 30)
        max_results = params.get("max_results", 100)
        date_str = self._get_date_filter(days_back)

        logger.info("Iniciando ingestão para %s alvos (janela: %s dias).", len(targets), days_back)
        for target_query in targets:
            final_query = f"{target_query} created:>{date_str}"
            repo_name = target_query.replace("repo:", "").replace(" is:issue", "").replace("/", "_")
            raw_data = self.fetch_github_issues(
                query=final_query,
                per_page=min(max_results, 100),
                max_results=max_results,
            )
            self.save_raw_data(raw_data, source_name=repo_name)


def main():
    IngestionEngine().run()


if __name__ == "__main__":
    main()
