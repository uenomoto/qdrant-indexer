# 設計ドキュメント — qdrant-indexer

## なぜ作ったか

### 課題

ソフトウェアプロジェクトの内部ドキュメント（設計書、ADR、ルール、スキル定義等）が増えると、**Grep では見つけられない情報**が出てくる。

- **表記揺れ**: 「認証」「auth」「ログイン」— 同じ概念でも Grep では全パターンを指定する必要がある
- **文脈**: 「Lambda のコールドスタート対策」を探したいが、ドキュメントには「初回起動遅延」としか書かれていない
- **分散**: 設計書 80+、ADR 30+、ドラフト 12+ にまたがる情報を横断検索するのが困難

### 解決策

**セマンティック検索**（意味ベースの検索）で解決する。ドキュメントをベクトルに変換して Qdrant に格納し、自然言語クエリで類似度検索する。

```
[ドキュメント] → [チャンク分割] → [ベクトル生成] → [Qdrant 格納]
                                                        ↓
[Claude Code] → [mcp-server-qdrant] → [自然言語クエリ] → [類似度検索] → [結果]
```

## アーキテクチャ

### ツール棲み分け

| 責務 | ツール |
|------|--------|
| コードの構造的読み書き | Serena（MCP サーバー） |
| **内部ドキュメントのセマンティック検索** | **qdrant-indexer + mcp-server-qdrant** |
| 外部ライブラリのドキュメント | Context7（MCP サーバー） |
| Web 上の技術情報 | Tavily / WebSearch |

### システム構成

```
ホストマシン（WSL2）
│
├── qdrant-indexer リポ
│   ├── docker-compose.qdrant.yml   ← 本番 Qdrant（常時起動・共有）
│   │   └── qdrant-shared ネットワーク
│   │       └── コレクション "megurip", "project-b", ...
│   │
│   ├── .devcontainer/              ← CLI 開発用
│   │   └── docker-compose.yml      ← テスト用 Qdrant 内蔵（本番とは独立）
│   └── src/qdrant_indexer/         ← CLI ソースコード
│
└── 各プロジェクト（例: Megurip）
    ├── .devcontainer/
    │   └── docker-compose.yml      ← qdrant-shared ネットワークに接続
    ├── qdrant-index.yaml           ← インデクサー設定
    ├── .qdrant-index-state.json    ← sync 用の状態（.gitignore）
    ├── docs/                       ← インデックス対象
    └── .claude/settings.json       ← mcp-server-qdrant 設定
```

**2種類の Qdrant**:
- **本番 Qdrant**（`docker-compose.qdrant.yml`）: 全プロジェクト共有。コレクション名でネームスペース分離。各プロジェクトの devcontainer が `qdrant-shared` 外部ネットワーク経由で接続
- **テスト Qdrant**（`.devcontainer/docker-compose.yml`）: CLI 開発・テスト用。本番とは完全独立

## 設計決定

### 埋め込みモデル: `intfloat/multilingual-e5-large`

| 項目 | 値 |
|------|-----|
| 次元数 | 1024 |
| サイズ | 2.24GB |
| 言語 | 100+ 言語対応 |
| ライセンス | MIT |

**選定理由**: 日本語と英語が混在するドキュメントに対応するため、多言語モデルを選択。精度最優先（速度 < 精度）。

**E5 プレフィックス**: E5 系モデルは投入テキストに `"passage: "` プレフィックス、検索クエリに `"query: "` プレフィックスを要求する。FastEmbed は自動付与しないため、`embedder.py` で対応している。

**将来候補**: `BAAI/bge-m3`（8192 トークン対応が魅力だが、FastEmbed Python の Dense 対応待ち）

### チャンク分割: h2 セクション区切り

- **分割単位**: `##`（h2 見出し）で分割
- **プレフィックス**: 各チャンクに `"ファイル名 > h1 > h2"` を付与し、検索結果の文脈を保持
- **短いセクション**: 50 トークン以下は前後のセクションとマージ
- **コードブロック保護**: ` ``` ` 内の `##` では分割しない

h3 以下は分割対象外（h2 セクション内に含まれる）。Markdown ドキュメントの一般的な構造（h1=タイトル、h2=章）に適合する粒度。

### 差分更新: git diff ベース

- `index` コマンド実行時に `.qdrant-index-state.json` に commit hash を記録
- `sync` コマンドは `git diff {last_commit}..HEAD -- '*.md'` で変更ファイルを検出
- 変更ファイルは旧チャンクを削除してから再投入（upsert）
- ファイル名リネームは「旧パス削除 + 新パス追加」として処理

### ポイント ID: 決定論的 UUID5

ファイルパス + セクションインデックスから UUID5 を生成する。同一ファイル・セクションの再投入時に同じ ID が生成されるため、Qdrant の upsert で自動的に上書きされる。

## モジュール構成

```
src/qdrant_indexer/
├── cli.py        # Typer CLI — 4コマンド（index/sync/status/delete）
├── config.py     # YAML 設定読み込み + バリデーション
├── chunker.py    # Markdown → h2 チャンク分割 + プレフィックス付与
├── embedder.py   # FastEmbed ラッパー — E5 プレフィックス自動付与
├── indexer.py    # Qdrant 投入/削除操作 — バッチ upsert + フィルタ削除
├── git_diff.py   # git diff ベースの変更ファイル検出
├── state.py      # .qdrant-index-state.json の読み書き
└── models.py     # dataclass: Chunk, ChunkMetadata, IndexState, Config 系
```

### 依存関係

```
cli.py
├── config.py     → models.py
├── chunker.py    → models.py
├── embedder.py   → models.py (Chunk)
├── indexer.py    → models.py (Chunk)
├── git_diff.py   (subprocess のみ)
└── state.py      → models.py (IndexState)
```

全モジュールが `models.py` のデータ型を共有し、循環依存はない。

## プロジェクト固有コードの排除

このツールは汎用 CLI として設計されている。特定プロジェクトに依存するコードは一切含まない。

| 項目 | 方針 |
|------|------|
| ファイルパス | `qdrant-index.yaml` の `sources` で定義 |
| カテゴリ名 | `qdrant-index.yaml` の `sources.category` で定義 |
| コレクション名 | `qdrant-index.yaml` の `qdrant.collection` で定義 |
| 埋め込みモデル | `qdrant-index.yaml` の `embedding.model` で定義 |
| Qdrant URL | `qdrant-index.yaml` の `qdrant.url` で定義 |

新しいプロジェクトで使う場合は、プロジェクトルートに `qdrant-index.yaml` を配置するだけでよい。

## テスト方針

| モジュール | テスト手法 | モック対象 |
|-----------|-----------|-----------|
| `chunker.py` | 純粋ロジックテスト | なし |
| `config.py` | ファイル I/O テスト | なし（tmp_path） |
| `state.py` | JSON I/O テスト | なし（tmp_path） |
| `embedder.py` | モックテスト | `fastembed.TextEmbedding` |
| `indexer.py` | モックテスト | `qdrant_client.QdrantClient` |
| `git_diff.py` | モックテスト | `subprocess.run` |

外部サービス（Qdrant、FastEmbed モデル）はモックでテストし、実 Qdrant での E2E テストは手動検証とする。

## 運用フロー

```bash
# 初回: 全ファイルを一括投入
qdrant-indexer index --config qdrant-index.yaml

# 日常: 変更ファイルだけ差分更新
qdrant-indexer sync --config qdrant-index.yaml

# モデル変更時: コレクション再構築
qdrant-indexer delete --config qdrant-index.yaml --force
qdrant-indexer index --config qdrant-index.yaml
```

`sync` を定期的に実行する仕組み（CI、git hook、Claude Code の `/gc` スキル(自作)等）を整備することで、検索対象を常に最新に保つ。

`http://localhost:6333/dashboard`でGUIでダッシュボードが見れる
