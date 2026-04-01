from __future__ import annotations

import unittest

from paper_analysis.evaluation.route_registry import build_default_route_registry


class RouteRegistryUnitTests(unittest.TestCase):
    def test_default_registry_exposes_four_stub_routes(self) -> None:
        registry = build_default_route_registry()

        self.assertEqual(
            [
                "embedding_similarity_binary",
                "llm_judge_stub",
                "local_classifier_stub",
                "two_stage_stub",
            ],
            registry.route_names(),
        )

    def test_default_registry_builds_stub_instances(self) -> None:
        registry = build_default_route_registry()

        routes = registry.create_routes()

        statuses = {route.route_name: route.implementation_status for route in routes}
        self.assertEqual("ready", statuses["embedding_similarity_binary"])
        self.assertEqual("stub", statuses["llm_judge_stub"])
        self.assertEqual("stub", statuses["local_classifier_stub"])
        self.assertEqual("stub", statuses["two_stage_stub"])
        self.assertEqual(4, len(routes))


if __name__ == "__main__":
    unittest.main()
