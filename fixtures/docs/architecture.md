# アーキテクチャ概要

qdrant-indexer は CLI、Embedder、Indexer の3層構成で設計されている。
各レイヤーは疎結合であり、単体テストが容易な構造となっている。
