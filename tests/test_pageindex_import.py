from pathlib import Path

import pytest

# 确保导入 lib 模块来配置 Python path


def test_import_pageindex():
    """验证可以导入 PageIndex 模块."""
    try:
        # PDF 处理：page_index 函数
        from pageindex import utils  # noqa: F401
        from pageindex.page_index import page_index

        # Markdown 处理：md_to_tree 函数（不是 page_index_md！）
        from pageindex.page_index_md import md_to_tree

        assert callable(page_index), "page_index 应该是可调用函数"
        assert callable(md_to_tree), "md_to_tree 应该是可调用函数"

        print("✓ PageIndex 模块导入成功")
        print(f"  - page_index (PDF): {page_index}")
        print(f"  - md_to_tree (Markdown): {md_to_tree}")
    except ImportError as e:
        pytest.fail(f"无法导入 PageIndex: {e}")


def test_load_config():
    """验证可以加载配置."""
    import yaml

    config_path = Path("config/pageindex_config.yaml")
    assert config_path.exists(), "配置文件不存在"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert "model" in config, "配置缺少 model 字段"
    assert config["model"] == "gpt-4o-2024-11-20", f"model 配置不正确: {config['model']}"
    assert config["if_add_doc_description"] == "yes", "未启用文档描述"

    print("✓ PageIndex 配置文件加载成功")
    print(f"  - model: {config['model']}")
    print(f"  - if_add_doc_description: {config['if_add_doc_description']}")
