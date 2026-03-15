"""インデックス状態の永続化（.qdrant-index-state.json）"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from qdrant_indexer.models import IndexState

logger = logging.getLogger(__name__)


def load_state(state_path: Path | str) -> IndexState | None:
    """状態ファイルを読み込む。存在しないか破損していれば None を返す。

    None が返った場合はフルインデックス（index コマンド）が必要。
    """
    path = Path(state_path)

    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("状態ファイルの読み込みに失敗。フルインデックスが必要です: %s", e)
        return None

    if not isinstance(raw, dict):
        logger.warning("状態ファイルのフォーマットが不正です")
        return None

    try:
        return IndexState(
            last_commit=raw["last_commit"],
            collection=raw["collection"],
            indexed_at=raw["indexed_at"],
            file_count=raw.get("file_count", 0),
            chunk_count=raw.get("chunk_count", 0),
        )
    except (KeyError, TypeError) as e:
        logger.warning("状態ファイルの必須フィールドが不足しています: %s", e)
        return None


def save_state(state_path: Path | str, state: IndexState) -> None:
    """状態ファイルを書き込む。"""
    path = Path(state_path)

    data = {
        "last_commit": state.last_commit,
        "collection": state.collection,
        "indexed_at": state.indexed_at,
        "file_count": state.file_count,
        "chunk_count": state.chunk_count,
    }

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
