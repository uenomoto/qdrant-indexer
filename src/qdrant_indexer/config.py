"""YAML 設定ファイルの読み込みとバリデーション"""

from __future__ import annotations

from pathlib import Path

import yaml

from qdrant_indexer.models import (
    EmbeddingConfig,
    IndexerConfig,
    QdrantConfig,
    SourceConfig,
)


class ConfigError(Exception):
    """設定ファイルの読み込み・バリデーションエラー"""


def load_config(config_path: Path | str) -> IndexerConfig:
    """YAML 設定ファイルを読み込み、IndexerConfig を返す。

    Args:
        config_path: qdrant-index.yaml のパス

    Returns:
        IndexerConfig: パース済みの設定オブジェクト

    Raises:
        ConfigError: ファイルが存在しない、YAML パースエラー、必須フィールド不足
    """
    path = Path(config_path)

    if not path.exists():
        msg = f"設定ファイルが見つかりません: {path}"
        raise ConfigError(msg)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        msg = f"YAML パースエラー: {path}: {e}"
        raise ConfigError(msg) from e

    if not isinstance(raw, dict):
        msg = f"設定ファイルのルートは辞書である必要があります: {path}"
        raise ConfigError(msg)

    return _parse_config(raw, path)


def _parse_config(raw: dict, config_path: Path) -> IndexerConfig:
    """生の辞書を IndexerConfig に変換する"""
    # qdrant セクション
    qdrant_raw = raw.get("qdrant")
    if not isinstance(qdrant_raw, dict):
        msg = f"'qdrant' セクションが必要です: {config_path}"
        raise ConfigError(msg)

    qdrant = QdrantConfig(
        url=_require_str(qdrant_raw, "url", "qdrant", config_path),
        collection=_require_str(qdrant_raw, "collection", "qdrant", config_path),
    )

    # embedding セクション
    embedding_raw = raw.get("embedding")
    if not isinstance(embedding_raw, dict):
        msg = f"'embedding' セクションが必要です: {config_path}"
        raise ConfigError(msg)

    embedding = EmbeddingConfig(
        model=_require_str(embedding_raw, "model", "embedding", config_path),
    )

    # sources セクション
    sources_raw = raw.get("sources")
    if not isinstance(sources_raw, list):
        msg = f"'sources' セクション（リスト）が必要です: {config_path}"
        raise ConfigError(msg)

    sources = []
    for i, src in enumerate(sources_raw):
        if not isinstance(src, dict):
            msg = f"sources[{i}] は辞書である必要があります: {config_path}"
            raise ConfigError(msg)
        sources.append(
            SourceConfig(
                path=_require_str(src, "path", f"sources[{i}]", config_path),
                category=_require_str(src, "category", f"sources[{i}]", config_path),
            )
        )

    if not sources:
        msg = f"'sources' に少なくとも1つのエントリが必要です: {config_path}"
        raise ConfigError(msg)

    return IndexerConfig(qdrant=qdrant, embedding=embedding, sources=sources)


def _require_str(data: dict, key: str, section: str, config_path: Path) -> str:
    """辞書から文字列フィールドを必須で取得する"""
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"'{section}.{key}' は空でない文字列が必要です: {config_path}"
        raise ConfigError(msg)
    return value
