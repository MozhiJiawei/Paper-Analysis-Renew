from __future__ import annotations

import json

from paper_analysis.services.annotation_repository import AnnotationRepository
from paper_analysis.services.annotator_selection import build_annotator, resolve_annotation_backend
from paper_analysis.shared.paths import ROOT_DIR


BENCHMARK_ROOT = ROOT_DIR / "data" / "benchmarks" / "paper-filter"


def annotate_benchmark() -> dict[str, object]:
    repository = AnnotationRepository(BENCHMARK_ROOT)
    backend = resolve_annotation_backend()
    annotator = build_annotator(backend)
    candidates = repository.load_candidates()
    existing_annotations = repository.load_annotations(repository.annotations_ai_path)
    annotations_by_id = {annotation.paper_id: annotation for annotation in existing_annotations}
    for candidate in candidates:
        if candidate.paper_id in annotations_by_id:
            continue
        annotations_by_id[candidate.paper_id] = annotator.annotate(candidate)
        repository.write_annotations(list(annotations_by_id.values()), repository.annotations_ai_path)
    return {
        "benchmark_root": str(BENCHMARK_ROOT),
        "total_records": len(candidates),
        "annotations_ai": len(annotations_by_id),
        "backend": backend,
    }


def main() -> None:
    summary = annotate_benchmark()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
