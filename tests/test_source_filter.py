"""_glob_to_regex / _match_source のテスト"""

from __future__ import annotations

import pytest

from qdrant_indexer.cli import _glob_to_regex, _match_source
from qdrant_indexer.models import SourceConfig


class TestGlobToRegex:
    """_glob_to_regex の変換テスト"""

    @pytest.mark.parametrize(
        ("pattern", "path", "expected"),
        [
            # ** は任意階層にマッチ
            ("docs/adr/**/*.md", "docs/adr/adr-001.md", True),
            ("docs/adr/**/*.md", "docs/adr/sub/adr-002.md", True),
            ("docs/adr/**/*.md", "docs/drafts/test.md", False),
            # * はディレクトリ区切りを超えない
            ("docs/*.md", "docs/readme.md", True),
            ("docs/*.md", "docs/sub/readme.md", False),
            # 拡張子違い
            ("docs/**/*.md", "docs/file.txt", False),
        ],
    )
    def test_パターンマッチ(self, pattern: str, path: str, expected: bool) -> None:
        import re

        regex = _glob_to_regex(pattern)
        assert bool(re.match(regex, path)) is expected


class TestMatchSource:
    """_match_source のカテゴリ解決テスト"""

    SOURCES = [
        SourceConfig(path="docs/adr/**/*.md", category="adr"),
        SourceConfig(path="docs/design/**/*.md", category="design"),
    ]

    def test_マッチすればカテゴリを返す(self) -> None:
        assert _match_source("docs/adr/adr-001.md", self.SOURCES) == "adr"
        assert _match_source("docs/design/foo.md", self.SOURCES) == "design"

    def test_マッチしなければNone(self) -> None:
        assert _match_source("docs/drafts/bar.md", self.SOURCES) is None
        assert _match_source("README.md", self.SOURCES) is None

    def test_先にマッチしたソースが優先(self) -> None:
        sources = [
            SourceConfig(path="docs/**/*.md", category="general"),
            SourceConfig(path="docs/adr/**/*.md", category="adr"),
        ]
        assert _match_source("docs/adr/adr-001.md", sources) == "general"
