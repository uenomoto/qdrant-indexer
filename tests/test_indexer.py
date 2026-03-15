"""indexer.py のテスト（qdrant_client をモック）"""

from unittest.mock import MagicMock, patch

from qdrant_indexer.indexer import QdrantIndexer, _generate_point_id
from qdrant_indexer.models import Chunk, ChunkMetadata


def _make_chunk(file_path: str, section: str, content: str) -> Chunk:
    return Chunk(
        content=content,
        metadata=ChunkMetadata(
            file_path=file_path,
            category="test",
            section=section,
            heading_path=f"{file_path} > {section}",
            updated_at="2026-03-15T10:00:00",
        ),
    )


class TestQdrantIndexer:
    """QdrantIndexer のテスト"""

    @patch("qdrant_indexer.indexer.QdrantClient")
    def test_ensure_collectionで新規作成(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.collection_exists.return_value = False

        indexer = QdrantIndexer("http://localhost:6333", "test-col", 1024)
        result = indexer.ensure_collection()

        assert result is True
        mock_client.create_collection.assert_called_once()

    @patch("qdrant_indexer.indexer.QdrantClient")
    def test_ensure_collectionで既存はスキップ(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.collection_exists.return_value = True

        indexer = QdrantIndexer("http://localhost:6333", "test-col", 1024)
        result = indexer.ensure_collection()

        assert result is False
        mock_client.create_collection.assert_not_called()

    @patch("qdrant_indexer.indexer.QdrantClient")
    def test_upsert_chunksがポイントを投入(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        indexer = QdrantIndexer("http://localhost:6333", "test-col", 3)
        chunks = [
            _make_chunk("doc.md", "背景", "背景テキスト"),
            _make_chunk("doc.md", "設計", "設計テキスト"),
        ]
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        result = indexer.upsert_chunks(chunks, vectors)

        assert result == 2
        mock_client.upsert.assert_called_once()

        # payload にメタデータが含まれている
        call_args = mock_client.upsert.call_args
        points = call_args.kwargs["points"]
        assert points[0].payload["file_path"] == "doc.md"
        assert points[0].payload["section"] == "背景"
        assert points[1].payload["section"] == "設計"

    @patch("qdrant_indexer.indexer.QdrantClient")
    def test_upsert_chunks空リストは0を返す(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        indexer = QdrantIndexer("http://localhost:6333", "test-col", 3)
        result = indexer.upsert_chunks([], [])

        assert result == 0
        mock_client.upsert.assert_not_called()

    @patch("qdrant_indexer.indexer.QdrantClient")
    def test_delete_by_fileがフィルタ付きで削除(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        indexer = QdrantIndexer("http://localhost:6333", "test-col", 3)
        indexer.delete_by_file("docs/old.md")

        mock_client.delete.assert_called_once()
        call_args = mock_client.delete.call_args
        assert call_args.kwargs["collection_name"] == "test-col"

    @patch("qdrant_indexer.indexer.QdrantClient")
    def test_delete_collectionが全削除(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        indexer = QdrantIndexer("http://localhost:6333", "test-col", 3)
        indexer.delete_collection()

        mock_client.delete_collection.assert_called_once_with("test-col")

    @patch("qdrant_indexer.indexer.QdrantClient")
    def test_get_collection_infoで存在するコレクション(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.collection_exists.return_value = True

        mock_info = MagicMock()
        mock_info.points_count = 42
        mock_info.indexed_vectors_count = 42
        mock_info.status = "green"
        mock_client.get_collection.return_value = mock_info

        indexer = QdrantIndexer("http://localhost:6333", "test-col", 3)
        info = indexer.get_collection_info()

        assert info["exists"] is True
        assert info["points_count"] == 42

    @patch("qdrant_indexer.indexer.QdrantClient")
    def test_get_collection_infoで存在しないコレクション(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.collection_exists.return_value = False

        indexer = QdrantIndexer("http://localhost:6333", "test-col", 3)
        info = indexer.get_collection_info()

        assert info["exists"] is False


class TestGeneratePointId:
    """_generate_point_id のテスト"""

    def test_同じ入力で同じIDが生成される(self) -> None:
        id1 = _generate_point_id("docs/test.md", 0)
        id2 = _generate_point_id("docs/test.md", 0)
        assert id1 == id2

    def test_異なる入力で異なるIDが生成される(self) -> None:
        id1 = _generate_point_id("docs/test.md", 0)
        id2 = _generate_point_id("docs/test.md", 1)
        id3 = _generate_point_id("docs/other.md", 0)
        assert id1 != id2
        assert id1 != id3
