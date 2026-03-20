from __future__ import annotations

import unittest

from paper_analysis.cli.common import CliInputError
from paper_analysis.sources.arxiv.atom_parser import parse_atom_feed
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
    <author><name>Ada</name></author>
    <author><name>Grace</name></author>
    <link href="http://arxiv.org/abs/2509.00001v1" rel="alternate" type="text/html" />
    <link title="pdf" href="http://arxiv.org/pdf/2509.00001v1" rel="related" type="application/pdf" />
    <arxiv:primary_category term="cs.AI" />
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom" />
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom" />
  </entry>
</feed>
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
        self.assertEqual(["cs.AI", "cs.LG"], paper.tags)
        self.assertEqual("2025-09-01", paper.published_at)
        self.assertEqual("http://arxiv.org/pdf/2509.00001v1", paper.pdf_url)


if __name__ == "__main__":
    unittest.main()
