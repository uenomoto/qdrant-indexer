# qdrant-indexer

内部 Markdown ドキュメントのセマンティック検索インデクサー CLI。

Qdrant ベクトル DB にドキュメントを投入し、[mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant) 経由で Claude Code からセマンティック検索を可能にする。

## 全体像

```
このリポジトリ（qdrant-indexer）
├── docker-compose.qdrant.yml   ← 本番 Qdrant（常時起動・全プロジェクト共有）
├── .devcontainer/              ← CLI 開発用（テスト用 Qdrant 内蔵）
└── src/qdrant_indexer/         ← CLI ソースコード

対象プロジェクト（例: Megurip）
├── qdrant-index.yaml           ← インデクサー設定（対象ファイル・コレクション名）
├── docs/                       ← インデックス対象のドキュメント
└── .devcontainer/
    └── docker-compose.yml      ← qdrant-shared ネットワークに接続
```

### 使い方フロー

```bash
# ① 本番 Qdrant を起動（初回のみ。以降は常時起動）
cd qdrant-indexer/
docker compose -f docker-compose.qdrant.yml up -d

# ② 対象プロジェクトの devcontainer を起動
cd megurip/
docker compose -f .devcontainer/docker-compose.yml up -d

# ③ devcontainer 内で CLI を実行してドキュメントを投入
docker exec -it megurip-infrastructure bash
uv tool install qdrant-indexer   # CLI をインストール（初回のみ）
qdrant-indexer index --config qdrant-index.yaml

# ④ Claude Code が mcp-server-qdrant 経由でセマンティック検索
#    → 自動で Qdrant に問い合わせて関連ドキュメントを返す
```

## セットアップ

### 本番 Qdrant の起動

```bash
# 初回のみ: 起動すると qdrant-shared ネットワークが自動作成される
docker compose -f docker-compose.qdrant.yml up -d

# 状態確認
curl http://localhost:6333/healthz
```

Qdrant は `restart: unless-stopped` で常時起動する。PC 再起動後も自動復帰。

### 対象プロジェクト側の設定

1. **docker-compose.yml に外部ネットワークを追加**:

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

2. **qdrant-index.yaml を作成**:

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

3. **mcp-server-qdrant を Claude Code に設定**:

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

## コマンド

```bash
# 全ファイルをインデックス（初回 or フルリビルド）
qdrant-indexer index --config qdrant-index.yaml

# 変更ファイルだけ差分更新（git diff ベース）
qdrant-indexer sync --config qdrant-index.yaml

# インデックスの状態を表示
qdrant-indexer status --config qdrant-index.yaml

# コレクションを削除
qdrant-indexer delete --config qdrant-index.yaml --force
```

| オプション | 対象コマンド | 説明 |
|-----------|-------------|------|
| `--config, -c` | 全コマンド | 設定ファイルのパス（デフォルト: `qdrant-index.yaml`） |
| `--dry-run` | index | チャンク分割 + ベクトル生成のみ、Qdrant への投入はスキップ |
| `--state` | sync, status | 状態ファイルのパス（デフォルト: `.qdrant-index-state.json`） |
| `--force, -f` | delete | 確認プロンプトをスキップ |

## 開発（CLI 自体の開発）

devcontainer にはテスト用 Qdrant が内蔵されている。本番 Qdrant とは独立。

```bash
# devcontainer 起動
docker volume create claude-code-config-qdrant-indexer  # 初回のみ
cp .devcontainer/devcontainer.env.example .devcontainer/devcontainer.env
docker compose -f .devcontainer/docker-compose.yml up -d
docker exec -it qdrant-indexer bash

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
