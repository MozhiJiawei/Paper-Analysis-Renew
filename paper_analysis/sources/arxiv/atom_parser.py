from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

from paper_analysis.cli.common import CliInputError
from paper_analysis.domain.paper import Paper

ATOM_NAMESPACE = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def parse_atom_feed(xml_data: bytes) -> list[Paper]:
    """Parse arXiv Atom feed payload into normalized Paper records."""

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise CliInputError("arXiv API 返回的 XML 无法解析") from exc

    papers: list[Paper] = []
    for entry in root.findall("atom:entry", ATOM_NAMESPACE):
        paper_id = _extract_text(entry, "atom:id").split("/abs/")[-1]
        title = _collapse_whitespace(_extract_text(entry, "atom:title"))
        abstract = _collapse_whitespace(_extract_text(entry, "atom:summary"))
        published_at = _format_published_at(_extract_text(entry, "atom:published"))
        authors = [
            _collapse_whitespace(author.text or "")
            for author in entry.findall("atom:author/atom:name", ATOM_NAMESPACE)
            if (author.text or "").strip()
        ]
        categories = [tag for tag in _extract_categories(entry) if tag]
        pdf_url = _find_link(entry, "application/pdf")

        papers.append(
            Paper(
                paper_id=paper_id,
                title=title,
                abstract=abstract,
                source="arxiv",
                venue="arXiv",
                authors=authors,
                tags=categories,
                organization="",
                published_at=published_at,
                primary_area=categories[0] if categories else "",
                keywords=categories,
                pdf_url=pdf_url,
                source_path="arxiv-api",
                raw_payload={"categories": categories, "authors": authors},
            )
        )
    return papers


def _extract_text(entry: ET.Element, path: str) -> str:
    node = entry.find(path, ATOM_NAMESPACE)
    if node is None or node.text is None or not node.text.strip():
        raise CliInputError(f"arXiv API 返回缺少字段：{path}")
    return node.text.strip()


def _extract_categories(entry: ET.Element) -> list[str]:
    categories = [
        category.attrib["term"]
        for category in entry.findall("atom:category", ATOM_NAMESPACE)
        if category.attrib.get("term")
    ]
    primary = entry.find("arxiv:primary_category", ATOM_NAMESPACE)
    if primary is None:
        return categories
    primary_term = primary.attrib.get("term", "").strip()
    if not primary_term:
        return categories
    if primary_term in categories:
        categories.remove(primary_term)
    return [primary_term, *categories]


def _find_link(entry: ET.Element, content_type: str) -> str:
    for link in entry.findall("atom:link", ATOM_NAMESPACE):
        if link.attrib.get("type") == content_type and link.attrib.get("href"):
            return link.attrib["href"]
    return ""


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _format_published_at(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return value
