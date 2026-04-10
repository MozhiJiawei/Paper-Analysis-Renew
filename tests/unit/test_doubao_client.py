from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paper_analysis.utils.doubao_client import DoubaoClient
from paper_analysis.utils.doubao_client import DoubaoUsage
from paper_analysis.utils.doubao_client import _chunk_list
from paper_analysis.utils.doubao_client import _merge_usage
from paper_analysis.utils.doubao_client import _should_use_multimodal_embedding_api


class DoubaoClientUnitTests(unittest.TestCase):
    def test_client_reads_embedding_model_from_private_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "doubao.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "doubao:",
                        "  api_key: test-key",
                        "  base_url: https://example.com/api/v3",
                        "  model: doubao-chat",
                        "  embedding_model: doubao-embedding-endpoint",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            client = DoubaoClient(config_path=config_path)

            self.assertEqual("doubao-chat", client.resolved_model)
            self.assertEqual("doubao-embedding-endpoint", client.resolved_embedding_model)

    def test_embed_texts_requires_embedding_model(self) -> None:
        client = DoubaoClient(
            config_path=Path("C:/does-not-exist/doubao.yaml"),
            api_key="test-key",
            base_url="https://example.com/api/v3",
            model="doubao-chat",
        )

        with self.assertRaisesRegex(ValueError, "embedding_model"):
            client.embed_texts(["hello"])

    def test_vision_embedding_model_uses_multimodal_fallback_signal(self) -> None:
        self.assertTrue(
            _should_use_multimodal_embedding_api(
                "doubao-embedding-vision-251215",
                RuntimeError("does not support this api"),
            )
        )
        self.assertFalse(
            _should_use_multimodal_embedding_api(
                "doubao-embedding-large-text-250515",
                RuntimeError("not found"),
            )
        )

    def test_chunk_list_splits_large_embedding_batches(self) -> None:
        chunks = _chunk_list(list(range(5)), 2)
        self.assertEqual([[0, 1], [2, 3], [4]], chunks)

    def test_merge_usage_accumulates_prompt_and_total_tokens(self) -> None:
        merged = _merge_usage(
            DoubaoUsage(prompt_tokens=10, total_tokens=12),
            DoubaoUsage(prompt_tokens=5, total_tokens=6),
        )
        self.assertIsNotNone(merged)
        assert merged is not None
        self.assertEqual(15, merged.prompt_tokens)
        self.assertEqual(18, merged.total_tokens)


if __name__ == "__main__":
    unittest.main()
