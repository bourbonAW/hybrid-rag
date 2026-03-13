#!/usr/bin/env python3
"""
LightRAG 集成验证脚本

运行此脚本验证 LightRAG 集成是否正常工作。
"""

import asyncio
from pathlib import Path

print("=" * 60)
print("LightRAG Integration Verification")
print("=" * 60)

# 1. 验证导入
print("\n[1/5] Checking imports...")
try:
    from lib.lightrag import LightRAGWrapper
    from services.document_service import DocumentService
    from services.global_search_service import GlobalSearchService
    print("  ✓ All imports successful")
except ImportError as e:
    print(f"  ✗ Import failed: {e}")
    exit(1)

# 2. 验证配置加载
print("\n[2/5] Checking configuration...")
try:
    wrapper = LightRAGWrapper()
    assert "llm" in wrapper.config
    assert "embedding" in wrapper.config
    assert "storage" in wrapper.config
    print(f"  ✓ Configuration loaded")
    print(f"    - Working dir: {wrapper.working_dir}")
    print(f"    - LLM model: {wrapper.config['llm']['model']}")
    print(f"    - Default mode: {wrapper.config['retrieval']['default_mode']}")
except Exception as e:
    print(f"  ✗ Configuration error: {e}")
    exit(1)

# 3. 验证初始化
print("\n[3/5] Checking initialization...")
try:
    asyncio.run(wrapper.initialize())
    print("  ✓ LightRAG initialized successfully")
except Exception as e:
    print(f"  ✗ Initialization failed: {e}")
    exit(1)

# 4. 验证基本功能
print("\n[4/5] Testing basic operations...")
try:
    # 测试索引
    test_text = """
    Apple Inc. is a technology company founded by Steve Jobs and Steve Wozniak.
    The company is headquartered in Cupertino, California.
    Apple is known for its iPhone, iPad, and Mac products.
    """
    result = asyncio.run(wrapper.index_document("verify_test_doc", test_text))
    print(f"  ✓ Document indexed: {result['document_id']}")
    
    # 测试搜索
    search_result = asyncio.run(wrapper.search("Who founded Apple?", mode="naive"))
    print(f"  ✓ Search completed (mode: {search_result['mode']})")
    print(f"    - Answer preview: {search_result['answer'][:100]}...")
    
except Exception as e:
    print(f"  ✗ Operation test failed: {e}")
    import traceback
    traceback.print_exc()
    # 不退出，继续清理

# 5. 验证关闭
print("\n[5/5] Checking cleanup...")
try:
    asyncio.run(wrapper.close())
    print("  ✓ Resources cleaned up")
except Exception as e:
    print(f"  ✗ Cleanup error: {e}")

print("\n" + "=" * 60)
print("Verification completed!")
print("=" * 60)
