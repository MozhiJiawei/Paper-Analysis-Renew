from __future__ import annotations

from paper_analysis.evaluation.routes.base import BaseBinaryRoute


class EmbeddingRetrieverStubRoute(BaseBinaryRoute):
    def __init__(self) -> None:
        super().__init__(
            route_name="embedding_retriever_stub",
            algorithm_version="ab-embedding-retriever-stub-v1",
            capability_type="embedding_retriever",
            implementation_status="stub",
        )
