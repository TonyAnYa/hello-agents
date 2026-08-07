"""测试离线诊断的基础行为。"""

from enterprise_concept_radar.diagnostics import (
    DiagnosticCheck,
    DiagnosticReport,
    check_environment,
)


def test_report_fails_only_for_fail_items() -> None:
    """警告不应让基础离线自检失败。"""
    report = DiagnosticReport(
        checks=(
            DiagnosticCheck(
                status="PASS",
                name="通过",
                message="ok",
            ),
            DiagnosticCheck(
                status="WARN",
                name="警告",
                message="warning",
            ),
        )
    )

    assert report.passed is True
    assert report.warning_count == 1
    assert report.failure_count == 0


def test_missing_env_is_warning_before_setup(
    tmp_path,
) -> None:
    """基础自检允许尚未创建 .env。"""
    check = check_environment(
        project_root=tmp_path,
        require_runtime=False,
    )

    assert check.status == "WARN"


def test_missing_env_fails_runtime_check(
    tmp_path,
) -> None:
    """正式运行自检必须要求 .env。"""
    check = check_environment(
        project_root=tmp_path,
        require_runtime=True,
    )

    assert check.status == "FAIL"


def test_environment_check_never_returns_values(
    tmp_path,
) -> None:
    """诊断信息只能显示缺失变量名，不能显示密钥值。"""
    secret = "super-secret-value"
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f"LLM_API_KEY={secret}",
                "LLM_MODEL_ID=model",
                "LLM_BASE_URL=https://example.com",
                "SERPAPI_API_KEY=search-key",
            ]
        ),
        encoding="utf-8",
    )
    check = check_environment(
        project_root=tmp_path,
        require_runtime=True,
    )

    assert check.status == "PASS"
    assert secret not in check.message
    assert "search-key" not in check.message
