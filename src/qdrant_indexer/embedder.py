"""FastEmbed を使ったベクトル生成ラッパー"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastembed import TextEmbedding

if TYPE_CHECKING:
    from qdrant_indexer.models import Chunk


class Embedder:
    """FastEmbed TextEmbedding のラッパー"""

    def __init__(self, model_name: str) -> None:
        """モデルをロードする。初回はモデルのダウンロードが発生する。

        Args:
            model_name: FastEmbed 対応モデル名（例: "intfloat/multilingual-e5-large"）
        """
        self._model = TextEmbedding(model_name=model_name)
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """チャンクリストのベクトルを一括生成する。

        Args:
            chunks: Chunk オブジェクトのリスト

        Returns:
            各チャンクに対応するベクトルのリスト
        """
        if not chunks:
            return []

        texts = [chunk.content for chunk in chunks]
        embeddings = list(self._model.embed(texts))
        return [embedding.tolist() for embedding in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """検索クエリのベクトルを生成する（テスト・デバッグ用）。

        Args:
            query: 検索クエリ文字列

        Returns:
            クエリのベクトル
        """
        embeddings = list(self._model.embed([query]))
        result: list[float] = embeddings[0].tolist()
        return result
