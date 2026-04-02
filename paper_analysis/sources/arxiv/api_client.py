from __future__ import annotations

import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from paper_analysis.cli.common import CliInputError

API_URL = "https://export.arxiv.org/api/query"
REQUEST_INTERVAL_SECONDS = 3.0
DEFAULT_USER_AGENT = "paper-analysis/1.0 (arxiv subscription ingestion)"

try:
    import certifi

    SSL_CONTEXT: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = None


class ArxivApiClient:
    """Minimal arXiv API client that respects the legacy API rate limit."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 30.0,
        request_interval_seconds: float = REQUEST_INTERVAL_SECONDS,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.request_interval_seconds = request_interval_seconds

    def fetch_feed(self, search_query: str, start: int, max_results: int) -> bytes:
        params = urllib.parse.urlencode(
            {
                "search_query": search_query,
                "start": start,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "ascending",
            }
        )
        request = urllib.request.Request(
            f"{API_URL}?{params}",
            headers={"User-Agent": self.user_agent},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=SSL_CONTEXT,
            ) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise CliInputError(f"arXiv API 请求失败，HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise CliInputError(f"无法连接 arXiv API：{exc.reason}") from exc
        except TimeoutError as exc:
            raise CliInputError("访问 arXiv API 超时") from exc
        except OSError as exc:
            raise CliInputError(f"访问 arXiv API 失败：{exc}") from exc

    def wait_for_next_request(self) -> None:
        time.sleep(self.request_interval_seconds)
