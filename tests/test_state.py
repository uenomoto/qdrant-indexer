"""state.py のテスト"""

from pathlib import Path

from qdrant_indexer.models import IndexState
from qdrant_indexer.state import load_state, save_state


class TestState:
    """state の読み書きテスト"""

    def test_保存と読み込みのラウンドトリップ(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state = IndexState(
            last_commit="abc123def456",
            collection="test-collection",
            indexed_at="2026-03-15T10:00:00+00:00",
            file_count=10,
            chunk_count=50,
        )

        save_state(state_path, state)
        loaded = load_state(state_path)

        assert loaded is not None
        assert loaded.last_commit == "abc123def456"
        assert loaded.collection == "test-collection"
        assert loaded.indexed_at == "2026-03-15T10:00:00+00:00"
        assert loaded.file_count == 10
        assert loaded.chunk_count == 50

    def test_存在しないファイルはNone(self, tmp_path: Path) -> None:
        result = load_state(tmp_path / "nonexistent.json")
        assert result is None

    def test_破損JSONはNone(self, tmp_path: Path) -> None:
        state_path = tmp_path / "broken.json"
        state_path.write_text("{ invalid json", encoding="utf-8")

        result = load_state(state_path)
        assert result is None

    def test_必須フィールド不足はNone(self, tmp_path: Path) -> None:
        state_path = tmp_path / "incomplete.json"
        state_path.write_text('{"last_commit": "abc"}', encoding="utf-8")

        result = load_state(state_path)
        assert result is None

    def test_ルートが辞書でない場合None(self, tmp_path: Path) -> None:
        state_path = tmp_path / "list.json"
        state_path.write_text("[1, 2, 3]", encoding="utf-8")

        result = load_state(state_path)
        assert result is None

    def test_オプションフィールドのデフォルト値(self, tmp_path: Path) -> None:
        state_path = tmp_path / "minimal.json"
        state_path.write_text(
            '{"last_commit": "abc", "collection": "test", "indexed_at": "2026-01-01"}',
            encoding="utf-8",
        )

        loaded = load_state(state_path)
        assert loaded is not None
        assert loaded.file_count == 0
        assert loaded.chunk_count == 0

    def test_文字列パスでも動作する(self, tmp_path: Path) -> None:
        state_path = tmp_path / "str.json"
        state = IndexState(
            last_commit="abc",
            collection="test",
            indexed_at="2026-01-01",
        )

        save_state(str(state_path), state)
        loaded = load_state(str(state_path))

        assert loaded is not None
        assert loaded.last_commit == "abc"
