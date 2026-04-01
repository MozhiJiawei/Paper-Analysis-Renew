from __future__ import annotations

import unittest

from paper_analysis.evaluation.route_registry import build_default_route_registry


class RouteRegistryUnitTests(unittest.TestCase):
    def test_default_registry_exposes_first_round_binary_ab_routes(self) -> None:
        registry = build_default_route_registry()

        self.assertEqual(
            [
                "embedding_retriever_stub",
                "local_classifier_stub",
                "rule_filtered_llm_binary",
                "two_stage_stub",
            ],
            registry.route_names(),
        )

    def test_default_registry_keeps_main_registry_deterministic_without_private_model_binding(self) -> None:
        registry = build_default_route_registry()

        routes = registry.create_routes()

        route_names = [route.route_name for route in routes]
        self.assertIn("rule_filtered_llm_binary", route_names)
        self.assertTrue(all(route.implementation_status == "stub" for route in routes))
        self.assertEqual(4, len(routes))


if __name__ == "__main__":
    unittest.main()
