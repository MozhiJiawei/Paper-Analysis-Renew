from __future__ import annotations

import unittest

from paper_analysis.cli.common import CliInputError
from paper_analysis.sources.arxiv.atom_parser import parse_atom_feed
from paper_analysis.sources.arxiv.email_loader import parse_arxiv_digest_text
from paper_analysis.sources.arxiv.subscription_loader import (
    _date_range,
    build_subscription_query,
)


SAMPLE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2509.00001v1</id>
    <updated>2025-09-01T00:00:00Z</updated>
    <published>2025-09-01T00:00:00Z</published>
    <title>Agent Systems in Practice</title>
    <summary>Example abstract.</summary>
    <author>
      <name>Ada</name>
      <arxiv:affiliation>OpenAI</arxiv:affiliation>
    </author>
    <author>
      <name>Grace</name>
      <arxiv:affiliation>Stanford University</arxiv:affiliation>
    </author>
    <link href="http://arxiv.org/abs/2509.00001v1" rel="alternate" type="text/html" />
    <link title="pdf" href="http://arxiv.org/pdf/2509.00001v1" rel="related" type="application/pdf" />
    <arxiv:primary_category term="cs.AI" />
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom" />
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom" />
  </entry>
</feed>
"""

SAMPLE_DIGEST = r"""------------------------------------------------------------------------------
 Submissions to:
Artificial Intelligence
 received from  Fri 22 May 26 18:00:00 GMT  to  Mon 25 May 26 18:00:00 GMT
------------------------------------------------------------------------------
\\
arXiv:2605.24306
Date: Sat, 23 May 2026 00:35:55 GMT   (40838kb)

Title: CoDA: Color Distribution Probing for Efficient and Generalizable
  AI-Generated Image Detection
Authors: Zexi Jia, Zhiqiang Yuan, Xiaoyue Duan, Jinchao Zhang, Jie Zhou, Anil
  K. Jain
Categories: cs.CV
\\
  AI-generated image detection faces a persistent trade-off between
generalization and efficiency.
\\ ( https://arxiv.org/abs/2605.24306 ,  40838kb)
------------------------------------------------------------------------------
\\
arXiv:2605.24326
Date: Sat, 23 May 2026 01:01:35 GMT   (37375kb)

Title: ScaleAcross Explorer: Exploring Communication Optimization for
  Scale-Across AI Model Training
Authors: Minghao Li, Alicia Golden, Samuel Hsia
Categories: cs.DC cs.AI cs.NI
\\
  The rapid scaling of large language model training requires distributing GPU
resources across multiple data center buildings and regions.
\\ ( https://arxiv.org/abs/2605.24326 ,  37375kb)
------------------------------------------------------------------------------
"""


class ArxivSubscriptionTests(unittest.TestCase):
    def test_date_range_parses_subscription_date(self) -> None:
        self.assertEqual(("202509010000", "202509012359"), _date_range("2025-09/09-01"))

    def test_date_range_rejects_invalid_date(self) -> None:
        with self.assertRaises(CliInputError):
            _date_range("2025-09-01")

    def test_build_subscription_query_uses_categories_and_date(self) -> None:
        query = build_subscription_query("2025-09/09-01", ["cs.AI", "cs.CL"])
        self.assertIn("cat:cs.AI OR cat:cs.CL", query)
        self.assertIn("submittedDate:[202509010000 TO 202509012359]", query)

    def test_parse_atom_feed_builds_normalized_paper(self) -> None:
        papers = parse_atom_feed(SAMPLE_FEED)

        self.assertEqual(1, len(papers))
        paper = papers[0]
        self.assertEqual("2509.00001v1", paper.paper_id)
        self.assertEqual("Agent Systems in Practice", paper.title)
        self.assertEqual(["Ada", "Grace"], paper.authors)
        self.assertEqual("OpenAI | Stanford University", paper.organization)
        self.assertEqual(["cs.AI", "cs.LG"], paper.tags)
        self.assertEqual("2025-09-01", paper.published_at)
        self.assertEqual("http://arxiv.org/pdf/2509.00001v1", paper.pdf_url)
        self.assertEqual(["OpenAI", "Stanford University"], paper.raw_payload["affiliations"])

    def test_parse_arxiv_digest_text_builds_papers_with_paper_dates(self) -> None:
        papers = parse_arxiv_digest_text(SAMPLE_DIGEST)

        self.assertEqual(2, len(papers))
        self.assertEqual("2605.24306", papers[0].paper_id)
        self.assertEqual("2026-05-23", papers[0].published_at)
        self.assertEqual("cs.CV", papers[0].primary_area)
        self.assertEqual(
            ["Zexi Jia", "Zhiqiang Yuan", "Xiaoyue Duan", "Jinchao Zhang", "Jie Zhou", "Anil K. Jain"],
            papers[0].authors,
        )
        self.assertIn("persistent trade-off", papers[0].abstract)
        self.assertEqual("https://arxiv.org/pdf/2605.24306", papers[0].pdf_url)


if __name__ == "__main__":
    unittest.main()
