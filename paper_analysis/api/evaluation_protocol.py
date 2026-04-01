from __future__ import annotations

from dataclasses import dataclass


PREFERENCE_LABELS = (
    "解码策略优化",
    "上下文与缓存优化",
    "系统与调度优化",
    "算子与内核优化",
    "模型结构侧推理优化",
    "模型压缩",
)

RESEARCH_OBJECT_LABELS = (
    "LLM",
    "多模态 / VLM",
    "Diffusion / 生成模型",
    "通用机器学习",
    "强化学习 / 序列决策",
    "检索 / 推荐 / 搜索",
    "计算机视觉",
    "语音 / 音频",
    "AI 系统 / 基础设施",
    "评测 / Benchmark / 数据集",
)

NEGATIVE_TIERS = ("positive", "negative")


class EvaluationProtocolError(ValueError):
    """Raised when an evaluation API payload violates the public schema."""


def _as_text(field_name: str, value: object, *, required: bool = True) -> str:
    if value is None:
        if required:
            raise EvaluationProtocolError(f"{field_name} 不能为空")
        return ""
    text = str(value).strip()
    if required and not text:
        raise EvaluationProtocolError(f"{field_name} 不能为空")
    return text


def _as_int(field_name: str, value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise EvaluationProtocolError(f"{field_name} 必须是整数") from exc


def _as_text_list(field_name: str, value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvaluationProtocolError(f"{field_name} 必须是字符串数组")
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _as_evidence_spans(value: object) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise EvaluationProtocolError("evidence_spans 必须是对象")
    normalized: dict[str, list[str]] = {}
    for key, raw_spans in value.items():
        label = str(key).strip()
        if label not in PREFERENCE_LABELS and label not in {"general", "negative"}:
            raise EvaluationProtocolError(f"evidence_spans 包含非法标签：{label}")
        normalized[label] = _as_text_list(f"evidence_spans[{label}]", raw_spans)
    return normalized


def validate_annotation_fields(
    *,
    primary_research_object: str,
    preference_labels: list[str],
    negative_tier: str,
    evidence_spans: dict[str, list[str]],
) -> None:
    if primary_research_object not in RESEARCH_OBJECT_LABELS:
        raise EvaluationProtocolError(
            f"primary_research_object 非法：{primary_research_object}"
        )
    invalid_labels = [item for item in preference_labels if item not in PREFERENCE_LABELS]
    if invalid_labels:
        raise EvaluationProtocolError(
            f"preference_labels 包含非法值：{', '.join(invalid_labels)}"
        )
    if negative_tier not in NEGATIVE_TIERS:
        raise EvaluationProtocolError(f"negative_tier 非法：{negative_tier}")
    if negative_tier == "positive" and len(preference_labels) != 1:
        raise EvaluationProtocolError("negative_tier=positive 时必须且只能返回一个 preference_label")
    if negative_tier == "negative" and preference_labels:
        raise EvaluationProtocolError("negative_tier=negative 时 preference_labels 必须为空")
    for label in evidence_spans:
        if label not in PREFERENCE_LABELS and label not in {"general", "negative"}:
            raise EvaluationProtocolError(f"evidence_spans 包含非法标签：{label}")


@dataclass(slots=True)
class EvaluationPaper:
    paper_id: str
    title: str
    abstract: str
    authors: list[str]
    venue: str
    year: int
    source: str
    source_path: str
    abstract_zh: str = ""
    keywords: list[str] | None = None

    def __post_init__(self) -> None:
        self.paper_id = _as_text("paper.paper_id", self.paper_id)
        self.title = _as_text("paper.title", self.title)
        self.abstract = _as_text("paper.abstract", self.abstract)
        self.abstract_zh = _as_text("paper.abstract_zh", self.abstract_zh, required=False)
        self.authors = _as_text_list("paper.authors", self.authors)
        self.venue = _as_text("paper.venue", self.venue)
        self.year = _as_int("paper.year", self.year)
        self.source = _as_text("paper.source", self.source)
        self.source_path = _as_text("paper.source_path", self.source_path)
        self.keywords = _as_text_list("paper.keywords", self.keywords or [])

    @classmethod
    def from_dict(cls, payload: object) -> EvaluationPaper:
        if not isinstance(payload, dict):
            raise EvaluationProtocolError("paper 必须是对象")
        return cls(
            paper_id=payload.get("paper_id"),
            title=payload.get("title"),
            abstract=payload.get("abstract"),
            abstract_zh=payload.get("abstract_zh", ""),
            authors=payload.get("authors", []),
            venue=payload.get("venue"),
            year=payload.get("year"),
            source=payload.get("source"),
            source_path=payload.get("source_path"),
            keywords=payload.get("keywords", []),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "abstract": self.abstract,
            "abstract_zh": self.abstract_zh,
            "authors": self.authors,
            "venue": self.venue,
            "year": self.year,
            "source": self.source,
            "source_path": self.source_path,
            "keywords": self.keywords or [],
        }


@dataclass(slots=True)
class EvaluationRequest:
    request_id: str
    paper: EvaluationPaper

    def __post_init__(self) -> None:
        self.request_id = _as_text("request_id", self.request_id)

    @classmethod
    def from_dict(cls, payload: object) -> EvaluationRequest:
        if not isinstance(payload, dict):
            raise EvaluationProtocolError("请求体必须是 JSON 对象")
        return cls(
            request_id=payload.get("request_id"),
            paper=EvaluationPaper.from_dict(payload.get("paper")),
        )


@dataclass(slots=True)
class EvaluationBatchRequest:
    requests: list[EvaluationRequest]

    def __post_init__(self) -> None:
        if not self.requests:
            raise EvaluationProtocolError("requests 必须是非空数组")

    @classmethod
    def from_dict(cls, payload: object) -> EvaluationBatchRequest:
        if not isinstance(payload, dict):
            raise EvaluationProtocolError("请求体必须是 JSON 对象")
        raw_requests = payload.get("requests")
        if not isinstance(raw_requests, list):
            raise EvaluationProtocolError("requests 必须是数组")
        return cls(
            requests=[EvaluationRequest.from_dict(item) for item in raw_requests],
        )


@dataclass(slots=True)
class EvaluationPrediction:
    primary_research_object: str
    preference_labels: list[str]
    negative_tier: str
    evidence_spans: dict[str, list[str]]
    notes: str = ""

    def __post_init__(self) -> None:
        self.primary_research_object = _as_text(
            "prediction.primary_research_object",
            self.primary_research_object,
        )
        self.preference_labels = _as_text_list(
            "prediction.preference_labels",
            self.preference_labels,
        )
        self.negative_tier = _as_text(
            "prediction.negative_tier",
            self.negative_tier,
        )
        self.evidence_spans = _as_evidence_spans(self.evidence_spans)
        self.notes = _as_text("prediction.notes", self.notes, required=False)
        validate_annotation_fields(
            primary_research_object=self.primary_research_object,
            preference_labels=self.preference_labels,
            negative_tier=self.negative_tier,
            evidence_spans=self.evidence_spans,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "primary_research_object": self.primary_research_object,
            "preference_labels": self.preference_labels,
            "negative_tier": self.negative_tier,
            "evidence_spans": self.evidence_spans,
            "notes": self.notes,
        }


@dataclass(slots=True)
class EvaluationResponse:
    request_id: str
    prediction: EvaluationPrediction
    algorithm_version: str

    def __post_init__(self) -> None:
        self.request_id = _as_text("request_id", self.request_id)
        self.algorithm_version = _as_text("algorithm_version", self.algorithm_version)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "prediction": self.prediction.to_dict(),
            "model_info": {"algorithm_version": self.algorithm_version},
        }


@dataclass(slots=True)
class EvaluationBatchResponse:
    responses: list[EvaluationResponse]

    def __post_init__(self) -> None:
        if not self.responses:
            raise EvaluationProtocolError("responses 必须是非空数组")

    def to_dict(self) -> dict[str, object]:
        return {"responses": [item.to_dict() for item in self.responses]}

