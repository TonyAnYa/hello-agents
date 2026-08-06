"""本地政策数据来源工具。"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from enterprise_concept_radar.models import PolicyDocument


class PolicySourceError(RuntimeError):
    """读取或校验政策来源失败。"""


def load_policy_document(
    file_path: str | Path,
) -> PolicyDocument:
    """从一个 JSON 文件中读取并校验政策文档。

    Args:
        file_path: 政策 JSON 文件路径。

    Returns:
        已完成校验的 PolicyDocument。

    Raises:
        PolicySourceError: 文件不存在、格式错误或字段校验失败。
    """
    path = Path(file_path)

    if not path.is_file():
        raise PolicySourceError(
            f"政策文件不存在：{path}"
        )

    if path.suffix.lower() != ".json":
        raise PolicySourceError(
            f"当前仅支持 JSON 政策文件：{path.name}"
        )

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            raw_data = json.load(file)
    except json.JSONDecodeError as exc:
        raise PolicySourceError(
            f"政策 JSON 格式错误：{path.name}；{exc}"
        ) from exc
    except OSError as exc:
        raise PolicySourceError(
            f"无法读取政策文件：{path}；{exc}"
        ) from exc

    try:
        return PolicyDocument.model_validate(raw_data)
    except ValidationError as exc:
        raise PolicySourceError(
            f"政策字段校验失败：{path.name}\n{exc}"
        ) from exc


def load_policy_directory(
    directory: str | Path,
) -> list[PolicyDocument]:
    """读取目录中的全部 JSON 政策文件。

    文件按照名称排序，以保证不同电脑上的执行顺序一致。
    """
    directory_path = Path(directory)

    if not directory_path.is_dir():
        raise PolicySourceError(
            f"政策目录不存在：{directory_path}"
        )

    json_files = sorted(
        directory_path.glob("*.json")
    )

    documents: list[PolicyDocument] = []

    for json_file in json_files:
        document = load_policy_document(json_file)
        documents.append(document)

    return documents