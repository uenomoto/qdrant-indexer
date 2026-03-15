"""データモデル定義（dataclass ベース）"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChunkMetadata:
    """チャンクに付随するメタデータ（Qdrant payload として保存）"""

    file_path: str  # 相対ファイルパス（例: "docs/adr/adr-001.md"）
    category: str  # 設定ファイルの sources.category（例: "design", "adr"）
    section: str  # h2 セクション名（例: "## 背景" → "背景"）
    heading_path: str  # "ファイル名 > h1 > h2" 形式のパンくずリスト
    updated_at: str  # ISO 8601 形式（例: "2026-03-15T10:00:00"）


@dataclass(frozen=True)
class Chunk:
    """分割されたドキュメントチャンク"""

    content: str  # プレフィックス付きテキスト本文
    metadata: ChunkMetadata


@dataclass
class IndexState:
    """インデックス状態（.qdrant-index-state.json に永続化）"""

    last_commit: str  # 前回インデックス時の git commit hash
    collection: str  # Qdrant コレクション名
    indexed_at: str  # ISO 8601 形式
    file_count: int = 0  # インデックス済みファイル数
    chunk_count: int = 0  # インデックス済みチャンク数


@dataclass(frozen=True)
class SourceConfig:
    """インデックス対象の glob パターン + カテゴリ"""

    path: str  # glob パターン（例: "docs/adr/**/*.md"）
    category: str  # カテゴリ名（例: "adr"）


@dataclass(frozen=True)
class QdrantConfig:
    """Qdrant 接続設定"""

    url: str  # Qdrant REST API URL（例: "http://localhost:6333"）
    collection: str  # コレクション名（例: "megurip"）


@dataclass(frozen=True)
class EmbeddingConfig:
    """埋め込みモデル設定"""

    model: str  # モデル名（例: "intfloat/multilingual-e5-large"）


@dataclass(frozen=True)
class IndexerConfig:
    """qdrant-index.yaml のトップレベル設定"""

    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    sources: list[SourceConfig] = field(default_factory=list)
