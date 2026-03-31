from __future__ import annotations

import unittest

from paper_analysis.evaluation.route_registry import build_default_route_registry


class RouteRegistryUnitTests(unittest.TestCase):
    def test_default_registry_exposes_four_stub_routes(self) -> None:
        registry = build_default_route_registry()

        self.assertEqual(
            [
                "embedding_retriever_stub",
                "llm_judge_stub",
                "local_classifier_stub",
                "two_stage_stub",
            ],
            registry.route_names(),
        )

    def test_default_registry_builds_stub_instances(self) -> None:
        registry = build_default_route_registry()

        routes = registry.create_routes()

        self.assertTrue(all(route.implementation_status == "stub" for route in routes))
        self.assertEqual(4, len(routes))


if __name__ == "__main__":
    unittest.main()
