"""Subscription-day paper loader backed by the official arXiv API."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from paper_analysis.cli.common import CliInputError
from paper_analysis.sources.arxiv.api_client import ArxivApiClient
from paper_analysis.sources.arxiv.atom_parser import parse_atom_feed

if TYPE_CHECKING:
    from paper_analysis.domain.paper import Paper

DEFAULT_CATEGORIES = ["cs.AI", "cs.CL", "cs.CV", "cs.DC", "cs.MA"]
DATE_PATTERN = re.compile(r"(\d{4})-(\d{2})/\d{2}-(\d{2})")


def load_subscription_papers(
    subscription_date: str,
    categories: list[str] | None = None,
    max_results: int = 10,
    client: ArxivApiClient | None = None,
) -> list[Paper]:
    """Fetch a bounded set of papers for a subscription day from arXiv API."""
    if max_results <= 0:
        raise CliInputError("--max-results 必须大于 0")

    search_query = build_subscription_query(subscription_date, categories)
    api_client = client or ArxivApiClient()
    papers: list[Paper] = []
    start = 0
    batch_size = min(max_results, 100)

    while len(papers) < max_results:
        xml_data = api_client.fetch_feed(
            search_query=search_query,
            start=start,
            max_results=min(batch_size, max_results - len(papers)),
        )
        batch = parse_atom_feed(xml_data)
        if not batch:
            break
        papers.extend(batch)
        if len(batch) < batch_size or len(papers) >= max_results:
            break
        start += len(batch)
        api_client.wait_for_next_request()

    return papers[:max_results]


def build_subscription_query(
    subscription_date: str,
    categories: list[str] | None = None,
) -> str:
    """Build the arXiv query string for one subscription day and category set."""
    start_date, end_date = _date_range(subscription_date)
    selected_categories = categories or DEFAULT_CATEGORIES
    category_query = " OR ".join(f"cat:{category}" for category in selected_categories)
    return f"({category_query}) AND submittedDate:[{start_date} TO {end_date}]"


def _date_range(subscription_date: str) -> tuple[str, str]:
    match = DATE_PATTERN.fullmatch(subscription_date)
    if match is None:
        raise CliInputError(
            f"非法订阅日期：{subscription_date}。期望格式为 YYYY-MM/MM-DD"
        )
    year, month, day = match.groups()
    date_token = f"{year}{month}{day}"
    return f"{date_token}0000", f"{date_token}2359"
