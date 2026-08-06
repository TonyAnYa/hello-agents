"""测试本地政策来源工具。"""

from pathlib import Path

import pytest

from enterprise_concept_radar.config import SAMPLE_POLICY_DIR
from enterprise_concept_radar.models import PolicyDocumentType
from enterprise_concept_radar.tools.policy_source import (
    PolicySourceError,
    load_policy_directory,
    load_policy_document,
)


def test_load_sample_policy_document() -> None:
    """应能读取并校验教学政策样本。"""
    policy_path = (
        SAMPLE_POLICY_DIR
        / "demo_policy_001.json"
    )

    document = load_policy_document(policy_path)

    assert document.document_id == "demo-policy-2026-001"
    assert document.document_type == PolicyDocumentType.NOTICE
    assert document.is_simulated is True
    assert document.source_name == "能源政策权威机构（教学模拟）"


def test_policy_keywords_are_deduplicated() -> None:
    """重复关键词应在模型校验时自动去重。"""
    policy_path = (
        SAMPLE_POLICY_DIR
        / "demo_policy_001.json"
    )

    document = load_policy_document(policy_path)

    assert document.keywords.count(
        "多用户绿电直连"
    ) == 1


def test_load_policy_directory() -> None:
    """应能按照稳定顺序读取政策目录。"""
    documents = load_policy_directory(
        SAMPLE_POLICY_DIR
    )

    assert len(documents) == 1
    assert documents[0].document_id == "demo-policy-2026-001"


def test_missing_policy_file_raises_error(
    tmp_path: Path,
) -> None:
    """文件不存在时应返回清晰的业务错误。"""
    missing_file = (
        tmp_path
        / "missing-policy.json"
    )

    with pytest.raises(
        PolicySourceError,
        match="政策文件不存在",
    ):
        load_policy_document(missing_file)
