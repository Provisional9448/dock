"""Dispatcher board fixtures. The assertion lives next to the JSONL."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_dispatcher_board_matches_mock() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "samples" / "board" / "check_board.py"
    spec = importlib.util.spec_from_file_location("dock_board_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.test_dispatcher_board()
