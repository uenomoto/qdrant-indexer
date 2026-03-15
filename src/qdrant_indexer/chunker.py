"""Markdown ファイルを h2 セクション単位でチャンク分割する"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from qdrant_indexer.models import Chunk, ChunkMetadata

# h2 分割の最小トークン数（これ以下のチャンクは前後とマージ）
MIN_CHUNK_TOKENS: int = 50


@dataclass
class _Section:
    """内部用: 分割されたセクション"""

    heading: str | None  # h2 見出しテキスト（None = 冒頭の見出しなし部分）
    content: str  # セクション本文


def chunk_markdown(
    content: str,
    file_path: str,
    category: str,
    updated_at: str,
) -> list[Chunk]:
    """Markdown を h2 セクションで分割し、Chunk リストを返す。

    Args:
        content: Markdown テキスト全文
        file_path: 相対ファイルパス
        category: カテゴリ名（design / adr / draft 等）
        updated_at: 最終更新日（ISO 8601）

    Returns:
        list[Chunk]: プレフィックス付きチャンクのリスト
    """
    if not content.strip():
        return []

    h1 = _extract_h1(content)
    sections = _split_by_h2(content)
    sections = _merge_short_sections(sections)

    file_name = Path(file_path).name

    chunks: list[Chunk] = []
    for section in sections:
        heading_path = _build_heading_path(file_name, h1, section.heading)
        prefixed_content = f"{heading_path}\n\n{section.content.strip()}"

        metadata = ChunkMetadata(
            file_path=file_path,
            category=category,
            section=section.heading or "(冒頭)",
            heading_path=heading_path,
            updated_at=updated_at,
        )

        chunks.append(Chunk(content=prefixed_content, metadata=metadata))

    return chunks


def _extract_h1(content: str) -> str | None:
    """最初の h1 見出しを抽出する。なければ None。"""
    match = re.search(r"^# (.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def _split_by_h2(content: str) -> list[_Section]:
    """h2（`## `）でコンテンツを分割する。

    コードブロック（```）内の `##` は分割しない。
    """
    sections: list[_Section] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    in_code_block = False

    for line in content.split("\n"):
        # コードブロックの開始/終了を追跡
        if line.strip().startswith("```"):
            in_code_block = not in_code_block

        # コードブロック外の h2 を検出
        if not in_code_block and re.match(r"^## (.+)$", line):
            # 現在のセクションを保存
            if current_lines:
                sections.append(
                    _Section(
                        heading=current_heading,
                        content="\n".join(current_lines),
                    )
                )
            # 新しいセクション開始
            current_heading = re.match(r"^## (.+)$", line).group(1).strip()  # type: ignore[union-attr]
            current_lines = []
        else:
            current_lines.append(line)

    # 最後のセクションを保存
    if current_lines:
        sections.append(
            _Section(
                heading=current_heading,
                content="\n".join(current_lines),
            )
        )

    return sections


def _merge_short_sections(sections: list[_Section]) -> list[_Section]:
    """短すぎるセクションを後続セクションにマージする。

    MIN_CHUNK_TOKENS 以下のセクションは次のセクションと結合する。
    最後のセクションが短い場合は前のセクションと結合する。
    """
    if len(sections) <= 1:
        return sections

    merged: list[_Section] = []
    pending: _Section | None = None

    for section in sections:
        if pending is not None:
            # pending が短い場合、現在のセクションとマージ
            if _estimate_tokens(pending.content) < MIN_CHUNK_TOKENS:
                heading = pending.heading or section.heading
                combined_content = pending.content.rstrip() + "\n\n" + section.content.lstrip()
                pending = _Section(heading=heading, content=combined_content)
            else:
                merged.append(pending)
                pending = section
        else:
            pending = section

    if pending is not None:
        # 最後の pending が短い場合、前のセクションとマージ
        if merged and _estimate_tokens(pending.content) < MIN_CHUNK_TOKENS:
            last = merged.pop()
            combined_content = last.content.rstrip() + "\n\n" + pending.content.lstrip()
            merged.append(_Section(heading=last.heading, content=combined_content))
        else:
            merged.append(pending)

    return merged


def _build_heading_path(
    file_name: str,
    h1: str | None,
    h2: str | None,
) -> str:
    """'ファイル名 > h1 > h2' 形式のパンくずリストを生成する。

    Args:
        file_name: ファイル名（拡張子付き）
        h1: h1 見出しテキスト（なければ None）
        h2: h2 見出しテキスト（なければ None）

    Returns:
        str: "file.md > Title > Section" 形式の文字列
    """
    parts = [file_name]
    if h1:
        parts.append(h1)
    if h2:
        parts.append(h2)
    return " > ".join(parts)


def _estimate_tokens(text: str) -> int:
    """簡易トークン数推定。

    日本語混在のため文字数 / 3 を概算値とする。
    正確さよりも閾値判定のための速度を優先。
    """
    return max(1, len(text) // 3)
