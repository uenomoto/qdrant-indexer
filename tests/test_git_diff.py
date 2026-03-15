"""git_diff.py のテスト（subprocess をモック）"""

from unittest.mock import patch

import pytest

from qdrant_indexer.git_diff import get_changed_files, get_current_commit


class TestGetCurrentCommit:
    """get_current_commit のテスト"""

    @patch("qdrant_indexer.git_diff.subprocess.run")
    def test_正常にコミットハッシュを取得(self, mock_run) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "abc123def456789\n"

        result = get_current_commit("/workspace")
        assert result == "abc123def456789"

    @patch("qdrant_indexer.git_diff.subprocess.run")
    def test_gitエラーでRuntimeError(self, mock_run) -> None:
        mock_run.return_value.returncode = 128
        mock_run.return_value.stderr = "fatal: not a git repository"

        with pytest.raises(RuntimeError, match="git rev-parse HEAD に失敗"):
            get_current_commit("/workspace")


class TestGetChangedFiles:
    """get_changed_files のテスト"""

    @patch("qdrant_indexer.git_diff.subprocess.run")
    def test_変更追加削除を正しくパース(self, mock_run) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "M\tdocs/design.md\n"
            "A\tdocs/new.md\n"
            "D\tdocs/old.md\n"
        )

        modified, deleted = get_changed_files("abc123", ["*.md"], "/workspace")

        assert modified == ["docs/design.md", "docs/new.md"]
        assert deleted == ["docs/old.md"]

    @patch("qdrant_indexer.git_diff.subprocess.run")
    def test_リネームを旧削除と新追加に変換(self, mock_run) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "R100\tdocs/old-name.md\tdocs/new-name.md\n"

        modified, deleted = get_changed_files("abc123", ["*.md"], "/workspace")

        assert "docs/new-name.md" in modified
        assert "docs/old-name.md" in deleted

    @patch("qdrant_indexer.git_diff.subprocess.run")
    def test_変更なしは空リスト(self, mock_run) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""

        modified, deleted = get_changed_files("abc123", ["*.md"], "/workspace")

        assert modified == []
        assert deleted == []

    @patch("qdrant_indexer.git_diff.subprocess.run")
    def test_gitエラーでRuntimeError(self, mock_run) -> None:
        mock_run.return_value.returncode = 128
        mock_run.return_value.stderr = "fatal: bad revision"

        with pytest.raises(RuntimeError, match="git diff に失敗"):
            get_changed_files("bad-hash", ["*.md"], "/workspace")
