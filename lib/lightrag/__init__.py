# lib/lightrag/__init__.py

"""LightRAG Module - Hybrid Search Practice.

基于 lightrag-hku v1.4.10 官方库的包装模块。
提供与 PageIndex 一致的接口风格，便于 GlobalSearchService 统一调用。
"""

from .wrapper import LightRAGWrapper

__version__ = "1.4.10"
__all__ = ["LightRAGWrapper"]
