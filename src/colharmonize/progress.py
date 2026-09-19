"""Small dependency-free progress reporting for long CLI runs."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import typer


def format_duration(seconds: float) -> str:
    """Format a duration compactly while retaining useful precision."""
    if seconds < 10:
        return f"{seconds:.1f}s"
    rounded = round(seconds)
    minutes, seconds_part = divmod(rounded, 60)
    if minutes < 60:
        return f"{minutes:d}m {seconds_part:02d}s"
    hours, minutes_part = divmod(minutes, 60)
    return f"{hours:d}h {minutes_part:02d}m {seconds_part:02d}s"


class RunReporter:
    """Report named stages and keep an interactive terminal visibly active."""

    _frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self, total_steps: int) -> None:
        self.total_steps = total_steps
        self.completed_steps = 0
        self.started_at = time.perf_counter()

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.started_at

    def _estimated_remaining(self, stage_elapsed: float = 0.0) -> float | None:
        if self.completed_steps == 0:
            return None
        completed_elapsed = max(self.elapsed - stage_elapsed, 0.0)
        mean_step = completed_elapsed / self.completed_steps
        return mean_step * (self.total_steps - self.completed_steps)

    @contextmanager
    def step(self, label: str) -> Iterator[None]:
        """Report one stage, including live elapsed time when attached to a terminal."""
        number = self.completed_steps + 1
        stage_started = time.perf_counter()
        typer.echo(f"[{number}/{self.total_steps}] {label}…", err=True)

        stop = threading.Event()
        thread: threading.Thread | None = None
        if sys.stderr.isatty():
            thread = threading.Thread(
                target=self._animate,
                args=(stop, stage_started),
                daemon=True,
            )
            thread.start()

        try:
            yield
        except BaseException:
            self._stop_animation(stop, thread)
            duration = time.perf_counter() - stage_started
            typer.echo(f"  Failed after {format_duration(duration)}", err=True)
            raise
        else:
            self._stop_animation(stop, thread)
            duration = time.perf_counter() - stage_started
            self.completed_steps += 1
            remaining = self._estimated_remaining()
            estimate = (
                f"; about {format_duration(remaining)} remaining" if remaining is not None else ""
            )
            typer.echo(
                f"  Done in {format_duration(duration)} "
                f"(elapsed {format_duration(self.elapsed)}{estimate})",
                err=True,
            )

    def _animate(self, stop: threading.Event, stage_started: float) -> None:
        frame_index = 0
        while not stop.wait(0.2):
            stage_elapsed = time.perf_counter() - stage_started
            remaining = self._estimated_remaining(stage_elapsed)
            estimate = (
                f" · about {format_duration(remaining)} remaining"
                if remaining is not None
                else " · estimating remaining time"
            )
            message = (
                f"\r  {self._frames[frame_index % len(self._frames)]} "
                f"elapsed {format_duration(self.elapsed)}{estimate}"
            )
            sys.stderr.write(message)
            sys.stderr.flush()
            frame_index += 1

    @staticmethod
    def _stop_animation(stop: threading.Event, thread: threading.Thread | None) -> None:
        stop.set()
        if thread is not None:
            thread.join()
            sys.stderr.write("\r\033[2K")
            sys.stderr.flush()
