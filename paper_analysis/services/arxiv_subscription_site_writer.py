"""Static site writer for arXiv subscription delivery runs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from paper_analysis.domain.delivery_run import DeliveryRunSnapshot

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
LATEST_TEMPLATE_NAME = "arxiv_subscription_latest.html.j2"
INDEX_TEMPLATE_NAME = "arxiv_subscription_index.html.j2"


def publish_subscription_site(
    *,
    snapshot: DeliveryRunSnapshot,
    archive_dir: Path,
    site_dir: Path,
    history_limit: int = 30,
) -> tuple[Path, Path, Path]:
    """Render latest/history pages, persist snapshots, and publish the site."""
    env = _build_environment()
    history_entries = _build_history_entries(snapshot, site_dir / "history.json", history_limit)

    latest_html = env.get_template(LATEST_TEMPLATE_NAME).render(snapshot=_serialize_snapshot(snapshot))
    index_html = env.get_template(INDEX_TEMPLATE_NAME).render(
        snapshot=_serialize_snapshot(snapshot),
        history_entries=history_entries,
        history_limit=history_limit,
    )
    history_json = json.dumps({"runs": history_entries}, ensure_ascii=False, indent=2)

    archive_latest_path = archive_dir / "latest.html"
    archive_index_path = archive_dir / "index.html"
    archive_history_path = archive_dir / "history.json"
    archive_latest_path.write_text(latest_html, encoding="utf-8")
    archive_index_path.write_text(index_html, encoding="utf-8")
    archive_history_path.write_text(history_json, encoding="utf-8")

    site_dir.mkdir(parents=True, exist_ok=True)
    published_latest_path = site_dir / "latest.html"
    published_index_path = site_dir / "index.html"
    published_history_path = site_dir / "history.json"
    shutil.copyfile(archive_latest_path, published_latest_path)
    shutil.copyfile(archive_index_path, published_index_path)
    shutil.copyfile(archive_history_path, published_history_path)
    return published_latest_path, published_index_path, published_history_path


def _build_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _build_history_entries(
    snapshot: DeliveryRunSnapshot,
    history_path: Path,
    history_limit: int,
) -> list[dict[str, object]]:
    existing_runs: list[dict[str, object]] = []
    if history_path.exists():
        payload = json.loads(history_path.read_text(encoding="utf-8"))
        raw_runs = payload.get("runs", [])
        if isinstance(raw_runs, list):
            existing_runs = [item for item in raw_runs if isinstance(item, dict)]

    current_entry = snapshot.history_entry()
    current_entry["site_status"] = "published"
    deduped_runs = [current_entry]
    deduped_runs.extend(item for item in existing_runs if item.get("run_id") != snapshot.run_id)
    return [_with_archive_links(item) for item in deduped_runs[:history_limit]]


def _serialize_snapshot(snapshot: DeliveryRunSnapshot) -> dict[str, object]:
    payload = snapshot.to_dict()
    steps = payload.get("steps", {})
    if isinstance(steps, dict) and isinstance(steps.get("site"), dict):
        steps["site"]["status"] = "published"
        steps["site"]["summary"] = "最新页与历史列表已发布。"
    return payload


def _with_archive_links(item: dict[str, object]) -> dict[str, object]:
    run_id = str(item.get("run_id", ""))
    if not run_id:
        return item
    enriched = dict(item)
    run_root = f"../runs/{run_id}"
    enriched["run_page_href"] = f"{run_root}/latest.html"
    enriched["history_page_href"] = f"{run_root}/index.html"
    enriched["email_page_href"] = f"{run_root}/email.html"
    enriched["snapshot_href"] = f"{run_root}/run.json"
    return enriched
