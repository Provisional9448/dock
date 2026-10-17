from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "samples"


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture
def sample_dir() -> Path:
    return SAMPLE
