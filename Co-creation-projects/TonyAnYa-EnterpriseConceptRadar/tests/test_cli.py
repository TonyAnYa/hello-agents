"""测试命令行环境检查功能。"""

from enterprise_concept_radar.cli import show_environment


def test_show_environment_prints_project_information(
    capsys,
) -> None:
    """环境检查应输出项目的必要信息。"""
    show_environment()

    captured = capsys.readouterr()
    output = captured.out

    assert "EnterpriseConceptRadar 环境检查" in output
    assert "项目版本：0.1.0" in output
    assert "Python：" in output
    assert "操作系统：" in output
    assert "项目根目录：" in output
    assert "基础环境检查完成" in output