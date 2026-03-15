# qdrant-indexer

内部 Markdown ドキュメントのセマンティック検索インデクサー CLI。

Qdrant ベクトル DB にドキュメントを投入し、[mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant) 経由で Claude Code からセマンティック検索を可能にする。

## 全体像
```
 WSL2（ホストマシン）
  │
  ├── ~/projects/qdrant-indexer/          ← CLI のソースコード
  │   ├── src/qdrant_indexer/             ← Python CLI 本体
  │   ├── docker-compose.qdrant.yml       ← ★ ローカル Qdrant を起動するファイル
  │   └── .devcontainer/                  ← CLI 開発用（今は停止）
  │
  ├── ~/projects/megurip/megurip_infrastructure/  ← ★ CLI を使う場所
  │   ├── docs/                           ← インデックス対象の設計書・ADR
  │   ├── qdrant-index.yaml               ← インデクサー設定
  │   └── .devcontainer/                  ← Megurip 開発コンテナ
  │
  │
  │  ┌─── Docker ネットワーク: qdrant-shared ───────────────────┐
  │  │                                                          │
  │  │  ┌──────────────────┐    ┌─────────────────────────────┐ │
  │  │  │  qdrant          │    │  megurip-infrastructure     │ │
  │  │  │  (Qdrant v1.17)  │◄───│  (Megurip devcontainer)     │ │
  │  │  │                  │    │                             │ │
  │  │  │  REST: 6333      │    │  qdrant-indexer CLI         │ │
  │  │  │  GUI: 6333/dash  │    │  (uv tool install で導入)   │ │
  │  │  │                  │    │                             │ │
  │  │  │  コレクション:     │    │  実行:                      │ │
  │  │  │   "megurip"      │    │  qdrant-indexer index       │ │
  │  │  │   "project-b"..  │    │  qdrant-indexer sync        │ │
  │  │  └──────────────────┘    └─────────────────────────────┘ │
  │  │         ↑                                                │
  │  └─────────│────────────────────────────────────────────────┘
  │            │
  │   http://localhost:6333/dashboard ← ブラウザから GUI 確認
  │
  └── Windows ブラウザ
```

## セットアップ

### 1. 本番 Qdrant の起動

```bash
# 初回のみ: 起動すると qdrant-shared ネットワークが自動作成される
cd projects/qdrant-indexer/ # 保存先によって変わる
docker compose -f docker-compose.qdrant.yml up -d
```

Qdrant は `restart: unless-stopped` で常時起動する。PC 再起動後も自動復帰。

### 2. 対象プロジェクト側の設定

**docker-compose.yml に外部ネットワークを追加**:

```yaml
services:
  app:
    networks:
      - your-project-network
      - qdrant-shared          # 追加

networks:
  your-project-network:
    ...
  qdrant-shared:               # 追加
    external: true
    name: qdrant-shared
```

meguripコンテナ起動後中に入って疎通確認
```sh
# 状態確認
curl -s http://qdrant:6333/healthz
```
ベクトルデータベースのサービス名がqdrantの場合
```sh
ping -c 3 qdrant
```

**qdrant-index.yaml を作成**:

```yaml
qdrant:
  url: "http://qdrant:6333"    # 共有ネットワーク内のコンテナ名で到達
  collection: "my-project"

embedding:
  model: "intfloat/multilingual-e5-large"

sources:
  - path: "docs/**/*.md"
    category: "design"
  - path: "adr/**/*.md"
    category: "adr"
```

**mcp-server-qdrant を Claude Code に設定**:

```json
{
  "mcpServers": {
    "qdrant": {
      "command": "uvx",
      "args": ["mcp-server-qdrant"],
      "env": {
        "QDRANT_URL": "http://qdrant:6333",
        "COLLECTION_NAME": "my-project",
        "EMBEDDING_MODEL": "intfloat/multilingual-e5-large"
      }
    }
  }
}
```

**重要**: CLI（投入側）と mcp-server-qdrant（検索側）で同じ埋め込みモデルを使うこと。一致しないと検索結果がおかしくなる。

### 3. CLI のインストール

PyPI に公開していないため、対象プロジェクトの devcontainer 内で git 経由でインストールする（初回のみ）。

```bash
# SSH 鍵の場合
uv tool install git+ssh://git@github.com/uenomoto/qdrant-indexer.git

# HTTPS の場合
uv tool install git+https://github.com/uenomoto/qdrant-indexer.git
```

## コマンド

### `index` — 全ファイルを一括インデックス

```bash
qdrant-indexer index --config qdrant-index.yaml
```

`qdrant-index.yaml` の `sources` に定義された全ファイルをチャンク分割・ベクトル化して Qdrant に投入する。初回セットアップや設定変更後のフルリビルドで使用。

### `sync` — 変更ファイルだけ差分更新

```bash
qdrant-indexer sync --config qdrant-index.yaml
```

`git diff` で前回インデックスからの変更を検出し、変更・追加されたファイルだけを再投入する。日常的な更新に使用。

### `status` — インデックス状態の確認

```bash
qdrant-indexer status --config qdrant-index.yaml
```

ローカルの状態ファイルと Qdrant のコレクション情報を表示する。

### `delete` — コレクション削除

```bash
qdrant-indexer delete --config qdrant-index.yaml --force
```

Qdrant のコレクションと `.qdrant-index-state.json` を削除する。`--force` を省略すると確認プロンプトが表示される。

### オプション一覧

| オプション | 対象コマンド | 説明 |
|-----------|-------------|------|
| `--config, -c` | 全コマンド | 設定ファイルのパス（デフォルト: `qdrant-index.yaml`） |
| `--dry-run` | index | チャンク分割 + ベクトル生成のみ、Qdrant への投入はスキップ |
| `--state` | sync, status | 状態ファイルのパス（デフォルト: `.qdrant-index-state.json`） |
| `--force, -f` | delete | 確認プロンプトをスキップ |

### 運用フロー

```bash
# 初回: 全ファイルを一括投入
qdrant-indexer index --config qdrant-index.yaml

# 日常: ドキュメント編集 → git commit → 差分更新
qdrant-indexer sync --config qdrant-index.yaml

# 設定変更時（sources 追加・モデル変更等）: フルリビルド
qdrant-indexer delete --config qdrant-index.yaml --force
qdrant-indexer index --config qdrant-index.yaml
```

> **注意**: `sync` は git diff ベースのため、**コミット済みの .md ファイルの変更のみ**を検出します。
> `qdrant-index.yaml` の `sources` にパスを追加しただけでは、既にコミット済みのファイルは sync の対象になりません。
> sources を変更した場合は `delete` → `index` でフルリビルドしてください。

## 確認方法

`http://localhost:6333/dashboard` の GUI サイドバーから Collections でポイント数やステータスを確認できる。

## 開発（CLI 自体の開発）

devcontainer にはテスト用 Qdrant が内蔵されている。本番 Qdrant とは独立。

```bash
# devcontainer 起動
docker compose up -d
docker compose exec {{サービス名}} bash

# テスト・Lint・型チェック
uv run pytest tests/ -xvs
uv run ruff check .
uv run ruff format .
uv run mypy src/qdrant_indexer/
```

## 注意事項

- **初回の `index` 実行時**、埋め込みモデル（約 2.24GB）のダウンロードが発生する
- `intfloat/multilingual-e5-large` は E5 系モデルのため、投入テキストに `"passage: "` プレフィックスが必要。本 CLI は自動で付与するので利用者は意識不要
- `.qdrant-index-state.json` は `.gitignore` に追加すること（ローカル状態のため）
- Qdrant を先に起動してから対象プロジェクトの devcontainer を起動すること（外部ネットワークが必要）
- `index` / `sync` 実行時に FastEmbed の mean pooling に関する `UserWarning` が表示されるが、**動作に影響はない**
