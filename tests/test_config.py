"""config.py のテスト"""

from pathlib import Path

import pytest

from qdrant_indexer.config import ConfigError, load_config


class TestLoadConfig:
    """load_config の正常系・異常系テスト"""

    def test_正常に全フィールドを読み込める(self, sample_config_path: Path) -> None:
        config = load_config(sample_config_path)

        assert config.qdrant.url == "http://localhost:6333"
        assert config.qdrant.collection == "test-collection"
        assert config.embedding.model == "intfloat/multilingual-e5-large"
        assert len(config.sources) == 2
        assert config.sources[0].path == "docs/**/*.md"
        assert config.sources[0].category == "design"
        assert config.sources[1].path == "adr/**/*.md"
        assert config.sources[1].category == "adr"

    def test_存在しないファイルでConfigError(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="設定ファイルが見つかりません"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_不正なYAMLでConfigError(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{ invalid yaml: [", encoding="utf-8")

        with pytest.raises(ConfigError, match="YAML パースエラー"):
            load_config(bad_yaml)

    def test_ルートが辞書でない場合ConfigError(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "list.yaml"
        bad_yaml.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ConfigError, match="ルートは辞書"):
            load_config(bad_yaml)

    def test_qdrantセクション不足でConfigError(self, tmp_path: Path) -> None:
        yaml_content = """
embedding:
  model: "test-model"
sources:
  - path: "docs/**/*.md"
    category: "design"
"""
        bad_yaml = tmp_path / "no-qdrant.yaml"
        bad_yaml.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="'qdrant' セクション"):
            load_config(bad_yaml)

    def test_embeddingセクション不足でConfigError(self, tmp_path: Path) -> None:
        yaml_content = """
qdrant:
  url: "http://localhost:6333"
  collection: "test"
sources:
  - path: "docs/**/*.md"
    category: "design"
"""
        bad_yaml = tmp_path / "no-embedding.yaml"
        bad_yaml.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="'embedding' セクション"):
            load_config(bad_yaml)

    def test_sourcesが空リストでConfigError(self, tmp_path: Path) -> None:
        yaml_content = """
qdrant:
  url: "http://localhost:6333"
  collection: "test"
embedding:
  model: "test-model"
sources: []
"""
        bad_yaml = tmp_path / "empty-sources.yaml"
        bad_yaml.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="少なくとも1つ"):
            load_config(bad_yaml)

    def test_必須フィールドが空文字でConfigError(self, tmp_path: Path) -> None:
        yaml_content = """
qdrant:
  url: ""
  collection: "test"
embedding:
  model: "test-model"
sources:
  - path: "docs/**/*.md"
    category: "design"
"""
        bad_yaml = tmp_path / "empty-url.yaml"
        bad_yaml.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="空でない文字列"):
            load_config(bad_yaml)

    def test_文字列パスでも読み込める(self, sample_config_path: Path) -> None:
        config = load_config(str(sample_config_path))
        assert config.qdrant.collection == "test-collection"
