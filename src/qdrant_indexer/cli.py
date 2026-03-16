"""Typer CLI エントリポイント — qdrant-indexer のコマンド定義"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from qdrant_indexer import __version__
from qdrant_indexer.chunker import chunk_markdown
from qdrant_indexer.config import ConfigError, load_config
from qdrant_indexer.embedder import Embedder
from qdrant_indexer.git_diff import get_changed_files, get_current_commit, get_repo_root
from qdrant_indexer.indexer import QdrantIndexer, derive_vector_name
from qdrant_indexer.models import Chunk, IndexState
from qdrant_indexer.state import load_state, save_state

_EMBED_BATCH_SIZE = 32


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"qdrant-indexer {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="qdrant-indexer",
    help="内部ドキュメントのセマンティック検索インデクサー CLI",
    no_args_is_help=True,
)


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="バージョンを表示",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """内部ドキュメントのセマンティック検索インデクサー CLI"""


def _resolve_files(sources: list, config_dir: Path) -> list[tuple[Path, str]]:
    """設定の sources から glob パターンを解決し、(ファイルパス, カテゴリ) のリストを返す"""
    files: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    for source in sources:
        for match in sorted(config_dir.glob(source.path)):
            path = Path(match)
            if path.is_file() and path not in seen:
                seen.add(path)
                files.append((path, source.category))

    return files


def _glob_to_regex(pattern: str) -> str:
    """glob パターンを正規表現に変換する（** と * をサポート）"""
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == '*':
            if i + 1 < len(pattern) and pattern[i + 1] == '*':
                # ** — 任意のディレクトリ階層
                parts.append(".*")
                i += 2
                # 直後の / をスキップ
                if i < len(pattern) and pattern[i] == '/':
                    i += 1
            else:
                # * — ディレクトリ区切りを除く任意の文字列
                parts.append("[^/]*")
                i += 1
        elif c == '?':
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(c))
            i += 1
    return "^" + "".join(parts) + "$"


def _match_source(rel_path: str, sources: list) -> str | None:
    """相対パスが sources のいずれかの glob パターンにマッチすればカテゴリを返す"""

    for source in sources:
        regex = _glob_to_regex(source.path)
        if re.match(regex, rel_path):
            return source.category
    return None


def _get_updated_at(file_path: Path) -> str:
    """ファイルの最終更新日を ISO 8601 形式で返す"""
    mtime = file_path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat()


def _embed_and_upsert(
    embedder: Embedder, qdrant: QdrantIndexer, chunks: list[Chunk]
) -> int:
    """チャンクをバッチ分割してベクトル生成 → Qdrant 投入する"""
    upserted = 0
    for start in range(0, len(chunks), _EMBED_BATCH_SIZE):
        batch_chunks = chunks[start : start + _EMBED_BATCH_SIZE]
        batch_vectors = embedder.embed_chunks(batch_chunks)
        upserted += qdrant.upsert_chunks(batch_chunks, batch_vectors)
    return upserted


def _save_index_state(
    config_dir: Path,
    state_path: Path,
    collection: str,
    file_count: int,
    chunk_count: int,
) -> None:
    """インデックス状態を保存する"""
    try:
        commit = get_current_commit(config_dir)
    except RuntimeError:
        commit = "unknown"

    state = IndexState(
        last_commit=commit,
        collection=collection,
        indexed_at=datetime.now(tz=UTC).isoformat(),
        file_count=file_count,
        chunk_count=chunk_count,
    )
    save_state(state_path, state)


@app.command()
def index(
    config: Path = typer.Option(
        "qdrant-index.yaml",
        "--config",
        "-c",
        help="設定ファイルのパス",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="チャンク分割とベクトル生成のみ実行し、Qdrant への投入はスキップ",
    ),
) -> None:
    """全ファイルをインデックス（初回 or フルリビルド）"""
    try:
        cfg = load_config(config)
    except ConfigError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e

    config_dir = config.resolve().parent

    # ファイル一覧を取得
    files = _resolve_files(cfg.sources, config_dir)
    if not files:
        typer.echo("対象ファイルが見つかりません")
        raise typer.Exit(code=1)

    typer.echo(f"対象ファイル: {len(files)} 件")

    # チャンク分割
    all_chunks: list[Chunk] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task("チャンク分割中...", total=len(files))
        for file_path, category in files:
            content = file_path.read_text(encoding="utf-8")
            rel_path = str(file_path.relative_to(config_dir))
            updated_at = _get_updated_at(file_path)

            chunks = chunk_markdown(content, rel_path, category, updated_at)
            all_chunks.extend(chunks)
            progress.advance(task)

    typer.echo(f"チャンク数: {len(all_chunks)} 件")

    if not all_chunks:
        typer.echo("チャンクが生成されませんでした")
        raise typer.Exit(code=1)

    # バッチ処理: ベクトル生成 → Qdrant 投入
    embedder = Embedder(cfg.embedding.model)
    qdrant: QdrantIndexer | None = None
    upserted_total = 0
    total_batches = (len(all_chunks) + _EMBED_BATCH_SIZE - 1) // _EMBED_BATCH_SIZE

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        desc = "ベクトル生成中..." if dry_run else "ベクトル生成 → 投入中..."
        task = progress.add_task(desc, total=total_batches)

        for start in range(0, len(all_chunks), _EMBED_BATCH_SIZE):
            batch_chunks = all_chunks[start : start + _EMBED_BATCH_SIZE]
            batch_vectors = embedder.embed_chunks(batch_chunks)

            if not dry_run:
                if qdrant is None:
                    qdrant = QdrantIndexer(
                        url=cfg.qdrant.url,
                        collection=cfg.qdrant.collection,
                        vector_size=len(batch_vectors[0]),
                        vector_name=derive_vector_name(cfg.embedding.model),
                    )
                    created = qdrant.ensure_collection()
                    if created:
                        typer.echo(f"コレクション '{cfg.qdrant.collection}' を作成しました")

                upserted_total += qdrant.upsert_chunks(batch_chunks, batch_vectors)

            progress.advance(task)

    if dry_run:
        typer.echo(f"[dry-run] ベクトル生成完了: {len(all_chunks)} 件")
        typer.echo("[dry-run] Qdrant への投入をスキップしました")
        return

    typer.echo(f"投入完了: {upserted_total} ポイント")

    # 状態を保存
    state_path = config_dir / ".qdrant-index-state.json"
    _save_index_state(config_dir, state_path, cfg.qdrant.collection, len(files), len(all_chunks))
    typer.echo(f"状態を保存しました: {state_path}")


@app.command()
def sync(
    config: Path = typer.Option(
        "qdrant-index.yaml",
        "--config",
        "-c",
        help="設定ファイルのパス",
    ),
    state_file: Path = typer.Option(
        ".qdrant-index-state.json",
        "--state",
        help="状態ファイルのパス",
    ),
) -> None:
    """変更ファイルだけ差分更新"""
    try:
        cfg = load_config(config)
    except ConfigError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e

    config_dir = config.resolve().parent
    current_state = load_state(state_file)

    if current_state is None:
        typer.echo("状態ファイルがありません。先に 'index' コマンドを実行してください。")
        raise typer.Exit(code=1)

    # 変更ファイルを検出
    try:
        modified, deleted = get_changed_files(
            last_commit=current_state.last_commit,
            source_patterns=["*.md"],
            repo_root=config_dir,
        )
    except RuntimeError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e

    if not modified and not deleted:
        typer.echo("変更なし")
        return

    # git リポジトリルートを取得してパスを変換
    git_root = get_repo_root(config_dir)

    # カテゴリマップを構築（index コマンドと同じ解決ロジック）
    all_source_files = _resolve_files(cfg.sources, config_dir)
    category_map = {
        str(fp.relative_to(config_dir)): cat for fp, cat in all_source_files
    }

    qdrant = QdrantIndexer(
        url=cfg.qdrant.url,
        collection=cfg.qdrant.collection,
        vector_size=0,  # 既存コレクション前提
        vector_name=derive_vector_name(cfg.embedding.model),
    )

    processed = 0
    skipped = 0

    # 削除ファイルのベクトルを削除（sources にマッチするもののみ）
    for del_file in deleted:
        abs_path = git_root / del_file
        try:
            rel_path = str(abs_path.relative_to(config_dir))
        except ValueError:
            skipped += 1
            continue
        if _match_source(rel_path, cfg.sources) is None:
            skipped += 1
            continue
        qdrant.delete_by_file(rel_path)
        processed += 1
        typer.echo(f"  削除: {rel_path}")

    # 変更ファイルを再インデックス
    if modified:
        embedder = Embedder(cfg.embedding.model)

        for mod_file in modified:
            abs_path = git_root / mod_file
            if not abs_path.exists():
                skipped += 1
                continue

            try:
                rel_path = str(abs_path.relative_to(config_dir))
            except ValueError:
                skipped += 1
                continue

            category = category_map.get(rel_path)
            if category is None:
                skipped += 1
                continue

            # 旧チャンクを削除してから再投入
            qdrant.delete_by_file(rel_path)

            content = abs_path.read_text(encoding="utf-8")
            updated_at = _get_updated_at(abs_path)
            chunks = chunk_markdown(content, rel_path, category, updated_at)

            if chunks:
                _embed_and_upsert(embedder, qdrant, chunks)

            processed += 1
            typer.echo(f"  更新: {rel_path} ({len(chunks)} チャンク)")

    detected = len(modified) + len(deleted)
    typer.echo(
        f"変更検出: {detected} 件（対象: {processed} 件, スキップ: {skipped} 件）"
    )

    # 状態を更新
    info = qdrant.get_collection_info()
    _save_index_state(
        config_dir,
        state_file,
        cfg.qdrant.collection,
        len(all_source_files),
        info.get("points_count", 0) if info.get("exists") else 0,
    )
    if processed > 0:
        typer.echo("状態を更新しました")
    else:
        typer.echo("対象ファイルなし。インデックスは変更されませんでした")


@app.command()
def status(
    config: Path = typer.Option(
        "qdrant-index.yaml",
        "--config",
        "-c",
        help="設定ファイルのパス",
    ),
    state_file: Path = typer.Option(
        ".qdrant-index-state.json",
        "--state",
        help="状態ファイルのパス",
    ),
) -> None:
    """現在のインデックス状態を表示"""
    try:
        cfg = load_config(config)
    except ConfigError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e

    # ローカル状態
    current_state = load_state(state_file)

    table = Table(title="qdrant-indexer status")
    table.add_column("項目", style="cyan")
    table.add_column("値", style="green")

    table.add_row("コレクション", cfg.qdrant.collection)
    table.add_row("Qdrant URL", cfg.qdrant.url)
    table.add_row("埋め込みモデル", cfg.embedding.model)
    table.add_row("ソース数", str(len(cfg.sources)))

    if current_state:
        table.add_row("最終コミット", current_state.last_commit[:12])
        indexed_at_display = current_state.indexed_at.replace("+00:00", "").replace("T", " ").split(".")[0] + " (UTC)" if current_state.indexed_at else ""
        table.add_row("インデックス日時", indexed_at_display)
        table.add_row("ファイル数", str(current_state.file_count))
        table.add_row("チャンク数", str(current_state.chunk_count))
    else:
        table.add_row("状態", "未インデックス")

    # Qdrant コレクション情報（接続できる場合のみ）
    try:
        qdrant = QdrantIndexer(
            url=cfg.qdrant.url,
            collection=cfg.qdrant.collection,
            vector_size=0,
            vector_name=derive_vector_name(cfg.embedding.model),
        )
        info = qdrant.get_collection_info()
        if info.get("exists"):
            table.add_row("Qdrant ポイント数", str(info.get("points_count", "?")))
            table.add_row("Qdrant ステータス", info.get("status", "?"))
        else:
            table.add_row("Qdrant", "コレクション未作成")
    except Exception:  # noqa: BLE001
        table.add_row("Qdrant", "接続失敗（Qdrant が起動していない可能性）")

    console = Console()
    console.print(table)


@app.command()
def delete(
    config: Path = typer.Option(
        "qdrant-index.yaml",
        "--config",
        "-c",
        help="設定ファイルのパス",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="確認プロンプトをスキップ",
    ),
) -> None:
    """コレクションを削除"""
    try:
        cfg = load_config(config)
    except ConfigError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e

    if not force:
        confirm = typer.confirm(
            f"コレクション '{cfg.qdrant.collection}' を削除しますか？"
        )
        if not confirm:
            typer.echo("キャンセルしました")
            raise typer.Exit(code=0)

    try:
        qdrant = QdrantIndexer(
            url=cfg.qdrant.url,
            collection=cfg.qdrant.collection,
            vector_size=0,
            vector_name=derive_vector_name(cfg.embedding.model),
        )
        qdrant.delete_collection()
        typer.echo(f"コレクション '{cfg.qdrant.collection}' を削除しました")
    except Exception as e:  # noqa: BLE001
        typer.echo(f"削除に失敗しました: {e}", err=True)
        raise typer.Exit(code=1) from e

    # 状態ファイルも削除
    config_dir = config.resolve().parent
    state_path = config_dir / ".qdrant-index-state.json"
    if state_path.exists():
        state_path.unlink()
        typer.echo(f"状態ファイルを削除しました: {state_path}")
