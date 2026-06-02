"""GROBID-backed affiliation enrichment for selected arXiv papers."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import TYPE_CHECKING

from paper_analysis.shared.paths import ARTIFACTS_DIR

if TYPE_CHECKING:
    from paper_analysis.domain.paper import Paper


DEFAULT_GROBID_BASE_URL = "http://127.0.0.1:8070"
DEFAULT_GROBID_CONTAINER_NAME = "paper-analysis-grobid"
DEFAULT_GROBID_DOCKER_IMAGE = "grobid/grobid:0.8.2"
GROBID_STARTUP_TIMEOUT_SECONDS = 120
GROBID_STARTUP_POLL_SECONDS = 5
HTTP_OK = 200
PDF_CACHE_DIR = ARTIFACTS_DIR / "cache" / "arxiv-pdfs"
REQUEST_TIMEOUT_SECONDS = 90
TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}
Downloader = Callable[[str, Path], bool]
GrobidClient = Callable[[Path, str], list[str]]
GrobidServiceStarter = Callable[[str], None]


@dataclass(slots=True)
class AffiliationEnrichmentResult:
    """Small status record for one affiliation enrichment attempt."""

    paper_id: str
    status: str
    organizations: list[str]
    error: str = ""


def enrich_selected_arxiv_papers_with_affiliations(  # noqa: PLR0913
    papers: list[Paper],
    *,
    grobid_base_url: str | None = None,
    cache_dir: Path = PDF_CACHE_DIR,
    downloader: Downloader | None = None,
    grobid_client: GrobidClient | None = None,
    grobid_service_starter: GrobidServiceStarter | None = None,
) -> list[AffiliationEnrichmentResult]:
    """Fill missing organizations for selected arXiv papers using PDF + GROBID.

    The function is best-effort: report generation should still succeed when a
    PDF cannot be downloaded or the local GROBID service is unavailable.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    base_url = (grobid_base_url or getenv("GROBID_BASE_URL") or DEFAULT_GROBID_BASE_URL).rstrip("/")
    download = downloader or download_pdf
    extract = grobid_client or extract_affiliations_with_grobid
    results: list[AffiliationEnrichmentResult] = []
    target_papers = [paper for paper in papers if not paper.organization and paper.pdf_url]
    if target_papers and grobid_client is None and _is_local_grobid_base_url(base_url):
        starter = grobid_service_starter or ensure_local_grobid_service
        try:
            starter(base_url)
        except OSError as exc:
            error = str(exc)
            for paper in papers:
                if paper.organization:
                    results.append(
                        AffiliationEnrichmentResult(
                            paper_id=paper.paper_id,
                            status="skipped-existing",
                            organizations=[paper.organization],
                        )
                    )
                    continue
                if not paper.pdf_url:
                    _record_enrichment_payload(paper, "skipped-missing-pdf", [])
                    results.append(
                        AffiliationEnrichmentResult(
                            paper_id=paper.paper_id,
                            status="skipped-missing-pdf",
                            organizations=[],
                        )
                    )
                    continue
                _record_enrichment_payload(paper, "grobid-unavailable", [], error)
                results.append(
                    AffiliationEnrichmentResult(
                        paper_id=paper.paper_id,
                        status="grobid-unavailable",
                        organizations=[],
                        error=error,
                    )
                )
            return results

    for paper in papers:
        if paper.organization:
            results.append(
                AffiliationEnrichmentResult(
                    paper_id=paper.paper_id,
                    status="skipped-existing",
                    organizations=[paper.organization],
                )
            )
            continue
        if not paper.pdf_url:
            _record_enrichment_payload(paper, "skipped-missing-pdf", [])
            results.append(
                AffiliationEnrichmentResult(
                    paper_id=paper.paper_id,
                    status="skipped-missing-pdf",
                    organizations=[],
                )
            )
            continue

        pdf_path = cache_dir / f"{_safe_file_stem(paper.paper_id)}.pdf"
        if not pdf_path.exists() and not download(paper.pdf_url, pdf_path):
            _record_enrichment_payload(paper, "pdf-download-failed", [])
            results.append(
                AffiliationEnrichmentResult(
                    paper_id=paper.paper_id,
                    status="pdf-download-failed",
                    organizations=[],
                )
            )
            continue

        try:
            organizations = extract(pdf_path, base_url)
        except (OSError, TimeoutError, ET.ParseError, urllib.error.URLError) as exc:
            _record_enrichment_payload(paper, "grobid-failed", [], str(exc))
            results.append(
                AffiliationEnrichmentResult(
                    paper_id=paper.paper_id,
                    status="grobid-failed",
                    organizations=[],
                    error=str(exc),
                )
            )
            continue

        if organizations:
            paper.organization = " | ".join(organizations)
            _record_enrichment_payload(paper, "ok", organizations)
            results.append(
                AffiliationEnrichmentResult(
                    paper_id=paper.paper_id,
                    status="ok",
                    organizations=organizations,
                )
            )
            continue

        _record_enrichment_payload(paper, "not-found", [])
        results.append(
            AffiliationEnrichmentResult(
                paper_id=paper.paper_id,
                status="not-found",
                organizations=[],
            )
        )

    return results


def ensure_local_grobid_service(grobid_base_url: str) -> None:
    """Start a local GROBID Docker container when the service is not ready."""
    if is_grobid_alive(grobid_base_url):
        return
    container_name = getenv("GROBID_CONTAINER_NAME") or DEFAULT_GROBID_CONTAINER_NAME
    image_name = getenv("GROBID_DOCKER_IMAGE") or DEFAULT_GROBID_DOCKER_IMAGE
    port = _local_grobid_port(grobid_base_url)
    try:
        existing = _run_docker(
            [
                "ps",
                "-a",
                "--filter",
                f"name=^{container_name}$",
                "--format",
                "{{.Names}}",
            ]
        )
        if container_name in existing.stdout.splitlines():
            _run_docker(["start", container_name])
        else:
            _run_docker(
                [
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-p",
                    f"{port}:8070",
                    image_name,
                ]
            )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise OSError(f"GROBID 服务未启动，且 Docker 自动启动失败：{exc}") from exc

    deadline = time.monotonic() + GROBID_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if is_grobid_alive(grobid_base_url):
            return
        time.sleep(GROBID_STARTUP_POLL_SECONDS)
    raise OSError(
        f"GROBID 容器已尝试启动，但 {GROBID_STARTUP_TIMEOUT_SECONDS} 秒内未就绪："
        f"{grobid_base_url}"
    )


def is_grobid_alive(grobid_base_url: str) -> bool:
    """Return whether the configured GROBID service answers the health endpoint."""
    try:
        with urllib.request.urlopen(  # noqa: S310 - configured local GROBID endpoint
            f"{grobid_base_url.rstrip('/')}/api/isalive",
            timeout=5,
        ) as response:
            return int(response.status) == HTTP_OK
    except (OSError, TimeoutError, urllib.error.URLError):
        return False


def download_pdf(pdf_url: str, output_path: Path) -> bool:
    """Download one PDF into the local cache."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(  # noqa: S310 - request targets paper.pdf_url from arXiv records
        pdf_url,
        headers={"User-Agent": "paper-analysis/0.1 affiliation-enrichment"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
            output_path.write_bytes(response.read())
    except (OSError, TimeoutError, urllib.error.URLError):
        return False
    return True


def extract_affiliations_with_grobid(pdf_path: Path, grobid_base_url: str) -> list[str]:
    """Extract affiliations with GROBID header first, then fulltext fallback."""
    header_url = f"{grobid_base_url}/api/processHeaderDocument"
    fulltext_url = f"{grobid_base_url}/api/processFulltextDocument"
    header_affiliations = post_pdf_to_grobid(pdf_path, header_url)
    if header_affiliations:
        return header_affiliations
    return post_pdf_to_grobid(pdf_path, fulltext_url)


def post_pdf_to_grobid(pdf_path: Path, url: str) -> list[str]:
    """POST a PDF to one GROBID endpoint and parse affiliation strings."""
    boundary = "----paper-analysis-grobid-boundary"
    pdf_bytes = pdf_path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="input"; filename="paper.pdf"\r\n',
            b"Content-Type: application/pdf\r\n\r\n",
            pdf_bytes,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(  # noqa: S310 - request targets configured local GROBID endpoint
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/xml",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
        return parse_grobid_affiliations(response.read())


def parse_grobid_affiliations(tei: bytes) -> list[str]:
    """Parse affiliation strings from a GROBID TEI document."""
    root = ET.fromstring(tei)  # noqa: S314 - TEI is produced by the trusted local GROBID service
    source_desc = root.find(".//tei:sourceDesc", TEI_NS)
    if source_desc is None:
        return []

    affiliations: list[str] = []
    seen: set[str] = set()
    for affiliation in source_desc.findall(".//tei:affiliation", TEI_NS):
        org_names = [
            _clean_text(" ".join(org.itertext()))
            for org in affiliation.findall(".//tei:orgName", TEI_NS)
        ]
        address_parts = [
            _clean_text(" ".join(node.itertext()))
            for node in affiliation.findall(".//tei:address/*", TEI_NS)
            if node.tag.rsplit("}", 1)[-1] in {"settlement", "region", "country"}
        ]
        value = _clean_text(", ".join(part for part in [*org_names, *address_parts] if part))
        if not value or value.casefold() in seen:
            continue
        seen.add(value.casefold())
        affiliations.append(value)
    return affiliations


def _record_enrichment_payload(
    paper: Paper,
    status: str,
    organizations: list[str],
    error: str = "",
) -> None:
    paper.raw_payload["affiliation_enrichment"] = {
        "provider": "grobid",
        "status": status,
        "organizations": organizations,
        "error": error,
    }


def _is_local_grobid_base_url(base_url: str) -> bool:
    normalized = base_url.rstrip("/")
    return normalized.startswith(("http://127.0.0.1:", "http://localhost:"))


def _local_grobid_port(base_url: str) -> str:
    match = re.search(r":(\d+)(?:/|$)", base_url)
    return match.group(1) if match else "8070"


def _run_docker(args: list[str]) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("docker")
    if not executable:
        raise OSError("找不到 docker 可执行文件")
    return subprocess.run(  # noqa: S603 - docker command is fixed; args are controlled by config.
        [executable, *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _safe_file_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "paper"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
