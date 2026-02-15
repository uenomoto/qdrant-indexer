# Megurip Docs - Claude Code プロジェクトルール

## プロジェクト概要

Megurip プロジェクトの学習記録・ADR・ドキュメントを PowerPoint 等にまとめるためのリポジトリ。

## ディレクトリ構造

```
source/    # 変換元の Markdown ファイルを置く
output/    # 生成された .pptx / .pdf を出力
```

## 開発ルール

- **コメント**: 日本語で記述
- **コミット**: feat/fix/docs/chore プレフィックス

## ワークフロー

1. `source/` に Markdown ファイルを配置
2. Claude に「スライドにして」と依頼
3. `output/` に .pptx が生成される
4. 必要に応じて PDF 変換も可能
