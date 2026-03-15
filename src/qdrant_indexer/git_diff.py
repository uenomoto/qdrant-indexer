"""git diff ベースの差分検知"""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_current_commit(repo_root: Path | str) -> str:
    """HEAD の commit hash を取得する。

    Args:
        repo_root: git リポジトリのルートディレクトリ

    Returns:
        HEAD の commit hash（40文字）

    Raises:
        RuntimeError: git コマンドが失敗した場合
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )

    if result.returncode != 0:
        msg = f"git rev-parse HEAD に失敗しました: {result.stderr.strip()}"
        raise RuntimeError(msg)

    return result.stdout.strip()


def get_repo_root(cwd: Path | str) -> Path:
    """git リポジトリのルートディレクトリを取得する。

    Args:
        cwd: 起点となるディレクトリ

    Returns:
        git リポジトリのルートディレクトリの Path

    Raises:
        RuntimeError: git コマンドが失敗した場合
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        check=False,
    )

    if result.returncode != 0:
        msg = f"git rev-parse --show-toplevel に失敗しました: {result.stderr.strip()}"
        raise RuntimeError(msg)

    return Path(result.stdout.strip())


def get_changed_files(
    last_commit: str,
    source_patterns: list[str],
    repo_root: Path | str,
) -> tuple[list[str], list[str]]:
    """git diff で前回コミットからの変更ファイルと削除ファイルを返す。

    Args:
        last_commit: 前回インデックス時の commit hash
        source_patterns: 対象の glob パターン（例: ["*.md"]）
        repo_root: git リポジトリのルートディレクトリ

    Returns:
        (modified_or_added, deleted): 変更/追加ファイルと削除ファイルのパスリスト

    Raises:
        RuntimeError: git コマンドが失敗した場合
    """
    cmd = [
        "git",
        "diff",
        "--name-status",
        f"{last_commit}..HEAD",
        "--",
        *source_patterns,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )

    if result.returncode != 0:
        msg = f"git diff に失敗しました: {result.stderr.strip()}"
        raise RuntimeError(msg)

    modified_or_added: list[str] = []
    deleted: list[str] = []

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue

        parts = line.split("\t")
        _min_parts = 2
        if len(parts) < _min_parts:
            continue

        status = parts[0]

        if status in ("M", "A"):
            modified_or_added.append(parts[1])
        elif status == "D":
            deleted.append(parts[1])
        elif status.startswith("R") and len(parts) >= _min_parts + 1:
            # リネーム: 旧パス削除 + 新パス追加
            deleted.append(parts[1])
            modified_or_added.append(parts[2])

    return modified_or_added, deleted
