"""embedder.py のテスト（FastEmbed をモック）"""

from unittest.mock import MagicMock, patch

import numpy as np

from qdrant_indexer.embedder import _PASSAGE_PREFIX, _QUERY_PREFIX, Embedder
from qdrant_indexer.models import Chunk, ChunkMetadata


def _make_chunk(content: str) -> Chunk:
    return Chunk(
        content=content,
        metadata=ChunkMetadata(
            file_path="test.md",
            category="test",
            section="test",
            heading_path="test.md > Test",
            updated_at="2026-03-15T10:00:00",
        ),
    )


class TestEmbedder:
    """Embedder のテスト"""

    @patch("qdrant_indexer.embedder.TextEmbedding")
    def test_embed_chunksでpassageプレフィックスが付与される(self, mock_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.embed.return_value = [np.array([0.1, 0.2, 0.3])]

        embedder = Embedder("test-model")
        chunks = [_make_chunk("テスト本文")]
        embedder.embed_chunks(chunks)

        # embed に渡されたテキストに "passage: " プレフィックスが付いている
        call_args = mock_instance.embed.call_args[0][0]
        assert call_args[0] == f"{_PASSAGE_PREFIX}テスト本文"

    @patch("qdrant_indexer.embedder.TextEmbedding")
    def test_embed_queryでqueryプレフィックスが付与される(self, mock_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.embed.return_value = [np.array([0.4, 0.5, 0.6])]

        embedder = Embedder("test-model")
        embedder.embed_query("検索クエリ")

        call_args = mock_instance.embed.call_args[0][0]
        assert call_args[0] == f"{_QUERY_PREFIX}検索クエリ"

    @patch("qdrant_indexer.embedder.TextEmbedding")
    def test_embed_chunksの戻り値がリストのリスト(self, mock_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.embed.return_value = [
            np.array([0.1, 0.2]),
            np.array([0.3, 0.4]),
        ]

        embedder = Embedder("test-model")
        chunks = [_make_chunk("chunk1"), _make_chunk("chunk2")]
        result = embedder.embed_chunks(chunks)

        assert len(result) == 2
        assert isinstance(result[0], list)
        assert result[0] == [0.1, 0.2]

    @patch("qdrant_indexer.embedder.TextEmbedding")
    def test_空リストは空リストを返す(self, mock_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        embedder = Embedder("test-model")
        result = embedder.embed_chunks([])

        assert result == []
        mock_instance.embed.assert_not_called()

    @patch("qdrant_indexer.embedder.TextEmbedding")
    def test_model_nameプロパティ(self, mock_cls: MagicMock) -> None:
        embedder = Embedder("intfloat/multilingual-e5-large")
        assert embedder.model_name == "intfloat/multilingual-e5-large"
