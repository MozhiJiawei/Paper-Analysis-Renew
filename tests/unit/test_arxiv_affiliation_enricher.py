from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_analysis.domain.paper import Paper
from paper_analysis.sources.arxiv.affiliation_enricher import (
    enrich_selected_arxiv_papers_with_affiliations,
    parse_grobid_affiliations,
)


SAMPLE_TEI = b"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <sourceDesc>
        <biblStruct>
          <analytic>
            <author>
              <affiliation>
                <orgName type="institution">Tencent WeChat AI</orgName>
                <address>
                  <settlement>Beijing</settlement>
                  <country>China</country>
                </address>
              </affiliation>
            </author>
            <author>
              <affiliation>
                <orgName type="department">Department of Computer Science and Engineering</orgName>
                <orgName type="institution">Michigan State University</orgName>
                <address>
                  <settlement>East Lansing</settlement>
                  <region>MI</region>
                  <country>USA</country>
                </address>
              </affiliation>
            </author>
          </analytic>
        </biblStruct>
      </sourceDesc>
    </fileDesc>
  </teiHeader>
</TEI>
"""


class ArxivAffiliationEnricherTests(unittest.TestCase):
    def test_parse_grobid_affiliations_reads_orgs_and_addresses(self) -> None:
        affiliations = parse_grobid_affiliations(SAMPLE_TEI)

        self.assertEqual(
            [
                "Tencent WeChat AI, Beijing, China",
                "Department of Computer Science and Engineering, Michigan State University, East Lansing, MI, USA",
            ],
            affiliations,
        )

    def test_enrich_selected_papers_downloads_and_updates_missing_organization(self) -> None:
        paper = Paper(
            paper_id="2605.24306",
            title="CoDA",
            abstract="Efficient detection.",
            source="arxiv",
            venue="arXiv",
            authors=["Ada"],
            tags=["cs.CV"],
            organization="",
            published_at="2026-05-23",
            pdf_url="https://arxiv.org/pdf/2605.24306",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)

            def fake_download(_url: str, output_path: Path) -> bool:
                output_path.write_bytes(b"%PDF-1.4")
                return True

            def fake_grobid(pdf_path: Path, base_url: str) -> list[str]:
                self.assertTrue(pdf_path.exists())
                self.assertEqual("http://grobid.test", base_url)
                return ["Tencent WeChat AI", "Michigan State University"]

            results = enrich_selected_arxiv_papers_with_affiliations(
                [paper],
                grobid_base_url="http://grobid.test",
                cache_dir=cache_dir,
                downloader=fake_download,
                grobid_client=fake_grobid,
            )

        self.assertEqual("Tencent WeChat AI | Michigan State University", paper.organization)
        self.assertEqual("ok", results[0].status)
        self.assertEqual("ok", paper.raw_payload["affiliation_enrichment"]["status"])

    def test_enrich_starts_local_grobid_before_processing(self) -> None:
        paper = Paper(
            paper_id="2605.24306",
            title="CoDA",
            abstract="Efficient detection.",
            source="arxiv",
            venue="arXiv",
            authors=["Ada"],
            tags=["cs.CV"],
            organization="",
            published_at="2026-05-23",
            pdf_url="https://arxiv.org/pdf/2605.24306",
        )
        starts: list[str] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)

            def fake_download(_url: str, output_path: Path) -> bool:
                output_path.write_bytes(b"%PDF-1.4")
                return True

            with patch(
                "paper_analysis.sources.arxiv.affiliation_enricher.extract_affiliations_with_grobid",
                return_value=["Started Lab"],
            ):
                results = enrich_selected_arxiv_papers_with_affiliations(
                    [paper],
                    grobid_base_url="http://127.0.0.1:8070",
                    cache_dir=cache_dir,
                    downloader=fake_download,
                    grobid_client=None,
                    grobid_service_starter=starts.append,
                )

        self.assertEqual(["http://127.0.0.1:8070"], starts)
        self.assertEqual("Started Lab", paper.organization)
        self.assertEqual("ok", results[0].status)

    def test_enrich_records_grobid_unavailable_when_start_fails(self) -> None:
        paper = Paper(
            paper_id="2605.24306",
            title="CoDA",
            abstract="Efficient detection.",
            source="arxiv",
            venue="arXiv",
            authors=["Ada"],
            tags=["cs.CV"],
            organization="",
            published_at="2026-05-23",
            pdf_url="https://arxiv.org/pdf/2605.24306",
        )

        results = enrich_selected_arxiv_papers_with_affiliations(
            [paper],
            grobid_base_url="http://127.0.0.1:8070",
            downloader=lambda _url, _path: self.fail("should not download without grobid"),
            grobid_service_starter=lambda _base_url: (_ for _ in ()).throw(
                OSError("docker unavailable")
            ),
        )

        self.assertEqual("", paper.organization)
        self.assertEqual("grobid-unavailable", results[0].status)
        self.assertEqual("grobid-unavailable", paper.raw_payload["affiliation_enrichment"]["status"])
        self.assertIn("docker unavailable", paper.raw_payload["affiliation_enrichment"]["error"])

    def test_enrich_selected_papers_skips_existing_organization(self) -> None:
        paper = Paper(
            paper_id="2605.24326",
            title="ScaleAcross",
            abstract="Serving.",
            source="arxiv",
            venue="arXiv",
            authors=["Ada"],
            tags=["cs.AI"],
            organization="Existing Lab",
            published_at="2026-05-23",
            pdf_url="https://arxiv.org/pdf/2605.24326",
        )

        results = enrich_selected_arxiv_papers_with_affiliations(
            [paper],
            downloader=lambda _url, _path: self.fail("should not download"),
        )

        self.assertEqual("Existing Lab", paper.organization)
        self.assertEqual("skipped-existing", results[0].status)


if __name__ == "__main__":
    unittest.main()
