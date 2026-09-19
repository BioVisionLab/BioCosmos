import sys
import time

import pytest

from harmonize_core.progress import RunReporter, format_duration


def test_format_duration_uses_readable_units() -> None:
    assert format_duration(0.04) == "0.0s"
    assert format_duration(9.94) == "9.9s"
    assert format_duration(65) == "1m 05s"
    assert format_duration(3_725) == "1h 02m 05s"


def test_interactive_spinner_does_not_repeat_stage_heading(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    reporter = RunReporter(total_steps=1)

    with reporter.step("Generate candidate matches"):
        time.sleep(0.25)

    output = capsys.readouterr().err
    assert output.count("Generate candidate matches") == 1
    assert "elapsed" in output
    assert "\r" in output
    assert "\x1b[2K" in output


def test_noninteractive_progress_has_no_terminal_control_sequences(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    reporter = RunReporter(total_steps=1)

    with reporter.step("Generate candidate matches"):
        pass

    output = capsys.readouterr().err
    assert output.count("Generate candidate matches") == 1
    assert "\r" not in output
    assert "\x1b" not in output
