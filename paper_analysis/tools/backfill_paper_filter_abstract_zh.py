from __future__ import annotations

import argparse
import json
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from paper_analysis.domain.benchmark import BenchmarkRecord
from paper_analysis.services.annotation_repository import AnnotationRepository
from paper_analysis.services.doubao_abstract_translator import DoubaoAbstractTranslator
from paper_analysis.shared.paths import ROOT_DIR


BENCHMARK_ROOT = ROOT_DIR / "data" / "benchmarks" / "paper-filter"
DEFAULT_WORKERS = 5
DEFAULT_CHECKPOINT_EVERY = 5


def backfill_abstract_zh(
    *,
    limit: int | None = None,
    workers: int = DEFAULT_WORKERS,
    checkpoint_every: int = DEFAULT_CHECKPOINT_EVERY,
) -> dict[str, object]:
    repository = AnnotationRepository(BENCHMARK_ROOT)
    translator = DoubaoAbstractTranslator()
    records = repository.load_records()
    pending_indexes = [index for index, record in enumerate(records) if _needs_backfill(record)]
    if limit is not None:
        pending_indexes = pending_indexes[:limit]

    if not pending_indexes:
        return {
            "benchmark_root": str(BENCHMARK_ROOT),
            "total_records": len(records),
            "updated_records": 0,
            "remaining_records": 0,
            "workers": workers,
            "checkpoint_every": checkpoint_every,
        }

    workers = max(1, workers)
    checkpoint_every = max(1, checkpoint_every)
    updated_records = list(records)
    translated_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending_futures: dict[Future[BenchmarkRecord], int] = {}
        pending_iter = iter(pending_indexes)

        for _ in range(min(workers, len(pending_indexes))):
            index = next(pending_iter, None)
            if index is None:
                break
            future = executor.submit(_translate_record, records[index], translator)
            pending_futures[future] = index

        while pending_futures:
            done, _ = wait(pending_futures.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                index = pending_futures.pop(future)
                translated_record = future.result()
                updated_records[index] = translated_record
                translated_count += 1

                if translated_count % checkpoint_every == 0:
                    repository.write_records(updated_records)

                next_index = next(pending_iter, None)
                if next_index is not None:
                    next_future = executor.submit(_translate_record, records[next_index], translator)
                    pending_futures[next_future] = next_index

    repository.write_records(updated_records)
    remaining_records = sum(1 for record in updated_records if _needs_backfill(record))
    return {
        "benchmark_root": str(BENCHMARK_ROOT),
        "total_records": len(records),
        "updated_records": translated_count,
        "remaining_records": remaining_records,
        "workers": workers,
        "checkpoint_every": checkpoint_every,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="为 paper-filter records.jsonl 回填中文摘要")
    parser.add_argument("--limit", type=int, default=None, help="本次最多回填多少条记录")
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"并发 worker 数，默认 {DEFAULT_WORKERS}",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=DEFAULT_CHECKPOINT_EVERY,
        help=f"每成功多少条落盘一次，默认 {DEFAULT_CHECKPOINT_EVERY}",
    )
    args = parser.parse_args()
    summary = backfill_abstract_zh(
        limit=args.limit,
        workers=args.workers,
        checkpoint_every=args.checkpoint_every,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _needs_backfill(record: BenchmarkRecord) -> bool:
    if not record.abstract.strip():
        return False
    if not record.abstract_zh.strip():
        return True
    # 覆盖测试或占位流程写入的伪中文摘要。
    return record.abstract_zh.strip() == f"中文摘要：{record.title}"


def _translate_record(
    record: BenchmarkRecord,
    translator: DoubaoAbstractTranslator,
) -> BenchmarkRecord:
    candidate = record.to_candidate_paper()
    abstract_zh = translator.translate(candidate)
    return BenchmarkRecord(
        paper_id=record.paper_id,
        title=record.title,
        abstract=record.abstract,
        abstract_zh=abstract_zh,
        authors=record.authors,
        venue=record.venue,
        year=record.year,
        source=record.source,
        source_path=record.source_path,
        primary_research_object=record.primary_research_object,
        candidate_preference_labels=record.candidate_preference_labels,
        candidate_negative_tier=record.candidate_negative_tier,
        keywords=record.keywords,
        notes=record.notes,
        final_primary_research_object=record.final_primary_research_object,
        final_preference_labels=record.final_preference_labels,
        final_negative_tier=record.final_negative_tier,
        final_labeler_ids=record.final_labeler_ids,
        final_review_status=record.final_review_status,
        final_evidence_spans=record.final_evidence_spans,
    )


if __name__ == "__main__":
    main()
