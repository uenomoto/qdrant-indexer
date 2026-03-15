"""chunker.py のテスト"""

from qdrant_indexer.chunker import chunk_markdown


class TestChunkMarkdown:
    """chunk_markdown のテスト"""

    def test_h2で正しく分割される(self, sample_md_content: str) -> None:
        chunks = chunk_markdown(
            content=sample_md_content,
            file_path="docs/sample.md",
            category="design",
            updated_at="2026-03-15T10:00:00",
        )

        # h2 セクションが複数あるので、複数チャンクが生成される
        # （短いセクションのマージにより、元の5セクションより少なくなる）
        assert len(chunks) >= 2

        # 各チャンクにメタデータが設定されている
        for chunk in chunks:
            assert chunk.metadata.file_path == "docs/sample.md"
            assert chunk.metadata.category == "design"
            assert chunk.metadata.updated_at == "2026-03-15T10:00:00"

    def test_プレフィックスが正しい形式(self, sample_md_content: str) -> None:
        chunks = chunk_markdown(
            content=sample_md_content,
            file_path="docs/sample.md",
            category="design",
            updated_at="2026-03-15T10:00:00",
        )

        # heading_path に "sample.md" が含まれる
        for chunk in chunks:
            assert "sample.md" in chunk.metadata.heading_path

        # h2 セクションのチャンクは "sample.md > サンプルドキュメント > セクション名" 形式
        h2_chunks = [c for c in chunks if c.metadata.section != "(冒頭)"]
        if h2_chunks:
            assert " > " in h2_chunks[0].metadata.heading_path

    def test_h1のみのファイル(self) -> None:
        content = "# タイトルのみ\n\n本文テキスト。\n"
        chunks = chunk_markdown(
            content=content,
            file_path="simple.md",
            category="draft",
            updated_at="2026-03-15T10:00:00",
        )

        assert len(chunks) == 1
        assert chunks[0].metadata.section == "(冒頭)"
        assert "simple.md > タイトルのみ" in chunks[0].metadata.heading_path

    def test_h2なしのファイル全体が1チャンク(self) -> None:
        content = "見出しなしのテキスト。\n\n段落1\n\n段落2\n"
        chunks = chunk_markdown(
            content=content,
            file_path="no-headings.md",
            category="rules",
            updated_at="2026-03-15T10:00:00",
        )

        assert len(chunks) == 1
        assert chunks[0].metadata.heading_path == "no-headings.md"

    def test_空コンテンツは空リスト(self) -> None:
        chunks = chunk_markdown(
            content="",
            file_path="empty.md",
            category="design",
            updated_at="2026-03-15T10:00:00",
        )
        assert chunks == []

    def test_空白のみのコンテンツは空リスト(self) -> None:
        chunks = chunk_markdown(
            content="   \n  \n  ",
            file_path="whitespace.md",
            category="design",
            updated_at="2026-03-15T10:00:00",
        )
        assert chunks == []

    def test_コードブロック内のh2で分割しない(self) -> None:
        content = """# テスト

## 本文セクション

テキスト。テスト用のダミーテキストを十分な長さで記述する。
このセクションは閾値を超えるために十分に長くする必要がある。
さらにテキストを追加して、MIN_CHUNK_TOKENS を確実に超える。
これで十分なはず。もう少し追加しておく。

```markdown
## これは分割しない
コードブロック内。
```

コードブロックの後のテキスト。
"""
        chunks = chunk_markdown(
            content=content,
            file_path="codeblock.md",
            category="design",
            updated_at="2026-03-15T10:00:00",
        )

        # "これは分割しない" が独立チャンクにならない
        section_names = [c.metadata.section for c in chunks]
        assert "これは分割しない" not in section_names

    def test_日本語コンテンツの処理(self) -> None:
        content = """# 日本語ドキュメント

## 認証・認可

ユーザー認証には Amazon Cognito を使用する。JWT トークンによるステートレスな認可を実現し、
API Gateway の Cognito Authorizer で検証する。トークンのリフレッシュは自動化されており、
フロントエンド側での明示的なトークン管理は不要。セッション管理はサーバーサイドで行わず、
全てのリクエストに認証情報を含める RESTful な設計を採用している。

## データベース設計

Neon PostgreSQL を採用し、サーバーレスアーキテクチャとの相性を最大限に活かしている。
Lambda のコールドスタート時のコネクション確立にかかる時間を最小限に抑えるため、
PgBouncer によるコネクションプーリングを使用。DDL 操作には Direct 接続を使用し、
PgBouncer を経由しない。マイグレーションは goose で管理する。
"""
        chunks = chunk_markdown(
            content=content,
            file_path="japanese.md",
            category="design",
            updated_at="2026-03-15T10:00:00",
        )

        # 冒頭 + 2つの h2 セクション（冒頭が短ければマージ）
        assert len(chunks) >= 2
        # 日本語テキストが正しく含まれている
        all_content = " ".join(c.content for c in chunks)
        assert "認証・認可" in all_content
        assert "データベース設計" in all_content

    def test_短いセクションのマージ(self) -> None:
        content = """# テスト

## セクション1

十分に長いセクション。テスト用のダミーテキストを複数行に渡って記述する。
これにより、MIN_CHUNK_TOKENS の閾値を超えることを確認する。
さらにテキストを追加して、十分なトークン数を確保する。
日本語テキストもそれなりのボリュームがないと、50トークンの閾値を超えない。
これで十分なはず。テスト用のテキスト追加分。追加テキスト。

## 短い

短。

## セクション3

別のセクション。こちらも十分な長さのテキスト。
テスト用のダミーテキストを複数行に渡って記述する。
さらにテキストを追加して、十分なトークン数を確保する。
追加のテキスト。閾値を超えるために記述する。十分なボリューム。
"""
        chunks = chunk_markdown(
            content=content,
            file_path="merge.md",
            category="design",
            updated_at="2026-03-15T10:00:00",
        )

        # "短い" セクションは前後にマージされるため、独立チャンクにならない
        section_names = [c.metadata.section for c in chunks]
        assert "短い" not in section_names

    def test_チャンクのcontentにプレフィックスが含まれる(self) -> None:
        content = """# タイトル

## セクションA

本文A。十分な長さのテキストを記述する。テスト用のダミーテキスト。
さらにテキストを追加する。閾値を超えるためのテキスト追加。
もう少し追加してトークン数を確保する。これで閾値は超えるはず。
"""
        chunks = chunk_markdown(
            content=content,
            file_path="prefix.md",
            category="adr",
            updated_at="2026-03-15T10:00:00",
        )

        for chunk in chunks:
            # content の先頭行が heading_path と一致する
            first_line = chunk.content.split("\n")[0]
            assert first_line == chunk.metadata.heading_path
