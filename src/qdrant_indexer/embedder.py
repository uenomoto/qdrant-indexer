"""FastEmbed を使ったベクトル生成ラッパー

E5 系モデル（intfloat/multilingual-e5-large 等）は、投入テキストに
"passage: " プレフィックス、検索クエリに "query: " プレフィックスを
付与する必要がある。FastEmbed は自動付与しないため、このモジュールで対応する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastembed import TextEmbedding

if TYPE_CHECKING:
    from qdrant_indexer.models import Chunk

# E5 モデルが要求するプレフィックス
_PASSAGE_PREFIX = "passage: "
_QUERY_PREFIX = "query: "


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

        E5 モデル用に "passage: " プレフィックスを自動付与する。

        Args:
            chunks: Chunk オブジェクトのリスト

        Returns:
            各チャンクに対応するベクトルのリスト
        """
        if not chunks:
            return []

        texts = [f"{_PASSAGE_PREFIX}{chunk.content}" for chunk in chunks]
        embeddings = list(self._model.embed(texts))
        return [embedding.tolist() for embedding in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """検索クエリのベクトルを生成する（テスト・デバッグ用）。

        E5 モデル用に "query: " プレフィックスを自動付与する。

        Args:
            query: 検索クエリ文字列

        Returns:
            クエリのベクトル
        """
        text = f"{_QUERY_PREFIX}{query}"
        embeddings = list(self._model.embed([text]))
        result: list[float] = embeddings[0].tolist()
        return result
