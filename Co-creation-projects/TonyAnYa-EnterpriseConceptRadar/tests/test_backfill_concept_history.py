"""测试历史报告回填的向后兼容解析。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]
SCRIPT_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "backfill_concept_history.py"
)


def load_backfill_module():
    """以脚本文件方式加载回填模块。"""
    spec = (
        importlib.util
        .spec_from_file_location(
            "backfill_concept_history_test",
            SCRIPT_PATH,
        )
    )
    assert spec is not None
    assert spec.loader is not None

    module = (
        importlib.util
        .module_from_spec(spec)
    )
    spec.loader.exec_module(module)
    return module


def test_legacy_computed_total_score_is_ignored(
    tmp_path: Path,
) -> None:
    """旧报告含 total_score 时仍应可回填解析。"""
    module = load_backfill_module()
    path = (
        tmp_path
        / "intelligence_run.json"
    )
    payload = {
        "task_id": "energy-policy-radar",
        "unexpected_future_field": {
            "anything": True,
        },
        "intelligence_items": [
            {
                "document_id": "doc-1",
                "policy_title": "测试政策",
                "policy_source_name": (
                    "国家能源局"
                ),
                "policy_source_url": (
                    "https://example.com/policy"
                ),
                "candidate": {
                    "term": (
                        "人工智能+电力应急"
                    ),
                    "detected_at": (
                        "2026-08-07T05:58:00Z"
                    ),
                    "novelty_score": 92,
                },
                "feedback_ranking": {
                    "ranking": {
                        "evaluations": [
                            {
                                "answer_id": (
                                    "answer-1"
                                ),
                                "total_score": (
                                    82.83
                                ),
                            }
                        ]
                    }
                },
            }
        ],
    }
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    run = (
        module.parse_intelligence_run(
            path
        )
    )

    assert (
        len(run.intelligence_items)
        == 1
    )
    assert (
        run.intelligence_items[
            0
        ].candidate.term
        == "人工智能+电力应急"
    )


def test_collection_parser_ignores_extra_fields(
    tmp_path: Path,
) -> None:
    """采集历史也只读取回填必需字段。"""
    module = load_backfill_module()
    path = (
        tmp_path
        / "collection_run.json"
    )
    payload = {
        "searched_candidate_count": 3,
        "documents": [
            {
                "document_id": "doc-1",
                "published_date": (
                    "2026-08-07"
                ),
                "title": "测试政策",
                "content": "历史完整正文",
            }
        ],
    }
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    run = (
        module.parse_collection_run(
            path
        )
    )

    assert len(run.documents) == 1
    assert (
        run.documents[0].document_id
        == "doc-1"
    )
    assert (
        run.documents[
            0
        ].published_date.isoformat()
        == "2026-08-07"
    )
