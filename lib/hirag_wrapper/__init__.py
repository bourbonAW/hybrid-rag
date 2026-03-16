# lib/hirag_wrapper/__init__.py

"""HiRAG Module - Hierarchical Knowledge RAG.

基于 HiRAG (https://github.com/hhy-huang/HiRAG) 官方库的包装模块。
提供与 PageIndex、LightRAG 一致的接口风格，便于 GlobalSearchService 统一调用。

References:
    - Paper: https://arxiv.org/abs/2503.10150
    - GitHub: https://github.com/hhy-huang/HiRAG
"""

from .wrapper import HiRAGWrapper

__version__ = "0.1.0"
__all__ = ["HiRAGWrapper"]
