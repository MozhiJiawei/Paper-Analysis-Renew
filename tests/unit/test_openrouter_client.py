from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from paper_analysis.utils.openrouter_client import OpenRouterClient
from paper_analysis.utils.openrouter_client import OpenRouterUsage
from paper_analysis.utils.openrouter_client import _chunk_list
from paper_analysis.utils.openrouter_client import _merge_usage


class OpenRouterClientUnitTests(unittest.TestCase):
    def test_client_reads_models_from_private_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "openrouter.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "openrouter:",
                        "  api_key: test-key",
                        "  base_url: https://example.com/api/v1",
                        "  chat_model: deepseek/deepseek-v4-pro",
                        "  embedding_model: qwen/qwen3-embedding-8b",
                        "  http_referer: https://example.com",
                        "  app_title: paper-analysis-test",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            client = OpenRouterClient(config_path=config_path)

            self.assertEqual("deepseek/deepseek-v4-pro", client.resolved_chat_model)
            self.assertEqual("qwen/qwen3-embedding-8b", client.resolved_embedding_model)
            self.assertEqual("https://example.com/api/v1", client.resolved_base_url)

    def test_submit_posts_chat_completion_payload(self) -> None:
        seen: dict[str, Any] = {}

        def transport(
            url: str,
            payload: dict[str, Any],
            headers: dict[str, str],
        ) -> dict[str, Any]:
            seen["url"] = url
            seen["payload"] = payload
            seen["headers"] = headers
            return {
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            audit_log_path = Path(temp_dir) / "audit.jsonl"
            client = OpenRouterClient(
                transport=transport,
                api_key="test-key",
                base_url="https://example.com/api/v1/",
                chat_model="deepseek/deepseek-v4-pro",
                config_path=Path("C:/does-not-exist/openrouter.yaml"),
                audit_log_path=audit_log_path,
            )

            result = client.submit([{"role": "user", "content": "ping"}]).result(timeout=5)

            self.assertTrue(result["success"])
            self.assertEqual('{"ok": true}', result["content"])
            self.assertEqual("https://example.com/api/v1/chat/completions", seen["url"])
            self.assertEqual("deepseek/deepseek-v4-pro", seen["payload"]["model"])
            self.assertEqual("Bearer test-key", seen["headers"]["Authorization"])
            audit_payload = json.loads(audit_log_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual("openrouter", audit_payload["provider"])
            self.assertEqual("deepseek/deepseek-v4-pro", audit_payload["model"])

    def test_embed_texts_posts_embedding_payload(self) -> None:
        seen: dict[str, Any] = {}

        def transport(
            url: str,
            payload: dict[str, Any],
            headers: dict[str, str],
        ) -> dict[str, Any]:
            seen["url"] = url
            seen["payload"] = payload
            seen["headers"] = headers
            return {
                "data": [
                    {"embedding": [0.1, 0.2]},
                    {"embedding": [0.3, 0.4]},
                ],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            }

        client = OpenRouterClient(
            transport=transport,
            api_key="test-key",
            embedding_model="qwen/qwen3-embedding-8b",
            config_path=Path("C:/does-not-exist/openrouter.yaml"),
        )

        response = client.embed_texts(["hello", "world"])

        self.assertTrue(response.success)
        self.assertEqual([[0.1, 0.2], [0.3, 0.4]], response.vectors)
        self.assertEqual("https://openrouter.ai/api/v1/embeddings", seen["url"])
        self.assertEqual("qwen/qwen3-embedding-8b", seen["payload"]["model"])
        self.assertEqual(["hello", "world"], seen["payload"]["input"])

    def test_embed_texts_requires_embedding_model(self) -> None:
        client = OpenRouterClient(
            api_key="test-key",
            embedding_model="",
            config_path=Path("C:/does-not-exist/openrouter.yaml"),
        )

        with self.assertRaisesRegex(ValueError, "embedding_model"):
            client.embed_texts(["hello"])

    def test_chunk_list_splits_large_embedding_batches(self) -> None:
        chunks = _chunk_list(list(range(5)), 2)
        self.assertEqual([[0, 1], [2, 3], [4]], chunks)

    def test_merge_usage_accumulates_prompt_and_total_tokens(self) -> None:
        merged = _merge_usage(
            OpenRouterUsage(prompt_tokens=10, total_tokens=12),
            OpenRouterUsage(prompt_tokens=5, total_tokens=6),
        )
        self.assertIsNotNone(merged)
        assert merged is not None
        self.assertEqual(15, merged.prompt_tokens)
        self.assertEqual(18, merged.total_tokens)


if __name__ == "__main__":
    unittest.main()
