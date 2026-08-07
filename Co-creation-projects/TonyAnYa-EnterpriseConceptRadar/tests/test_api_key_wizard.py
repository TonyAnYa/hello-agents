"""测试客户可见 API Key 输入的 Y/N 交互。"""

from scripts.configure_api_keys import (
    ask_visible_secret,
    ask_yes_no,
)


def test_yes_no_uses_default(
    monkeypatch,
) -> None:
    """直接回车应采用默认值。"""
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "",
    )

    assert ask_yes_no(
        "确认？",
        default=True,
    ) is True


def test_visible_secret_can_be_reentered(
    monkeypatch,
    capsys,
) -> None:
    """用户选择 N 后应重新填写，并在屏幕显示输入值。"""
    answers = iter(
        [
            "wrong-key-123456",
            "n",
            "correct-key-654321",
            "y",
        ]
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: next(answers),
    )

    value = ask_visible_secret(
        label="测试 API Key"
    )
    output = capsys.readouterr().out

    assert value == "correct-key-654321"
    assert "wrong-key-123456" in output
    assert "correct-key-654321" in output
