"""テスト共通フィクスチャ"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """fixtures ディレクトリのパスを返す"""
    return FIXTURES_DIR


@pytest.fixture
def sample_config_path(fixtures_dir: Path) -> Path:
    """テスト用 qdrant-index.yaml のパスを返す"""
    return fixtures_dir / "qdrant-index.yaml"


@pytest.fixture
def sample_md_path(fixtures_dir: Path) -> Path:
    """テスト用 sample.md のパスを返す"""
    return fixtures_dir / "sample.md"


@pytest.fixture
def sample_md_content(sample_md_path: Path) -> str:
    """テスト用 sample.md の内容を返す"""
    return sample_md_path.read_text(encoding="utf-8")
