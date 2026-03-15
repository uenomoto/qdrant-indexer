"""Qdrant コレクションへの投入・削除操作"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from qdrant_indexer.models import Chunk

# upsert のバッチサイズ
_BATCH_SIZE = 100


def derive_vector_name(model_name: str) -> str:
    """埋め込みモデル名から名前付きベクトルフィールド名を導出する。

    qdrant-client の FastEmbed 命名規則に準拠:
    ``model.split("/")[-1].lower()`` → ``f"fast-{name}"``

    Args:
        model_name: モデル名（例: "intfloat/multilingual-e5-large"）

    Returns:
        ベクトルフィールド名（例: "fast-multilingual-e5-large"）
    """
    short = model_name.rsplit("/", maxsplit=1)[-1].lower()
    return f"fast-{short}"


class QdrantIndexer:
    """Qdrant コレクションへのベクトル投入・削除"""

    def __init__(self, url: str, collection: str, vector_size: int, vector_name: str) -> None:
        """Qdrant クライアントを初期化する。

        Args:
            url: Qdrant REST API URL（例: "http://localhost:6333"）
            collection: コレクション名
            vector_size: ベクトルの次元数（例: 1024）
            vector_name: 名前付きベクトルフィールド名（例: "fast-multilingual-e5-large"）
        """
        self._client = QdrantClient(url=url)
        self._collection = collection
        self._vector_size = vector_size
        self._vector_name = vector_name

    def ensure_collection(self) -> bool:
        """コレクションが存在しなければ作成する。

        Returns:
            True: 新規作成した / False: 既に存在
        """
        if self._client.collection_exists(self._collection):
            return False

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                self._vector_name: VectorParams(
                    size=self._vector_size,
                    distance=Distance.COSINE,
                ),
            },
        )
        return True

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> int:
        """チャンクをベクトル付きで upsert する。

        ポイント ID は file_path + section_index の UUID5 ハッシュで生成。
        同一ファイル・セクションの再投入時に自動で上書きされる。

        Args:
            chunks: Chunk オブジェクトのリスト
            vectors: 対応するベクトルのリスト

        Returns:
            投入したポイント数
        """
        if not chunks:
            return 0

        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            point_id = _generate_point_id(chunk.metadata.file_path, i)
            payload = {
                "file_path": chunk.metadata.file_path,
                "category": chunk.metadata.category,
                "section": chunk.metadata.section,
                "heading_path": chunk.metadata.heading_path,
                "updated_at": chunk.metadata.updated_at,
                "document": chunk.content,
            }
            points.append(PointStruct(id=point_id, vector={self._vector_name: vector}, payload=payload))

        # バッチ分割して投入
        for start in range(0, len(points), _BATCH_SIZE):
            batch = points[start : start + _BATCH_SIZE]
            self._client.upsert(
                collection_name=self._collection,
                points=batch,
            )

        return len(points)

    def delete_by_file(self, file_path: str) -> None:
        """指定ファイルの全チャンクを削除する。

        Args:
            file_path: 削除対象のファイルパス
        """
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="file_path",
                        match=MatchValue(value=file_path),
                    )
                ]
            ),
        )

    def delete_collection(self) -> None:
        """コレクション全体を削除する。"""
        self._client.delete_collection(self._collection)

    def get_collection_info(self) -> dict[str, Any]:
        """コレクションの統計情報を取得する。

        Returns:
            points_count, status 等を含む辞書
        """
        if not self._client.collection_exists(self._collection):
            return {"exists": False, "collection": self._collection}

        info = self._client.get_collection(self._collection)
        return {
            "exists": True,
            "collection": self._collection,
            "points_count": info.points_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "status": str(info.status),
        }


def _generate_point_id(file_path: str, section_index: int) -> str:
    """ファイルパスとセクションインデックスから決定論的な UUID を生成する。

    同じファイル・セクションの再投入時に同じ ID が生成されるため、
    upsert で自動的に上書きされる。
    """
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID namespace URL
    key = f"{file_path}#{section_index}"
    return str(uuid.uuid5(namespace, hashlib.sha256(key.encode()).hexdigest()))
