# lib/lightrag/wrapper.py

"""
LightRAG 包装层 - 基于 lightrag-hku 官方库

职责：
1. 适配 lightrag-hku API 到项目统一接口
2. 配置管理（从 YAML 读取配置，传递给 LightRAG）
3. 多文档查询封装（lightrag-hku 原生支持单 workspace 多文档）
4. 统计信息获取（用于监控和调试）

注意：
- 所有核心功能（分块、实体提取、图构建、检索）都由 lightrag-hku 提供
- 本模块只提供包装和配置，不实现核心算法
"""

import os
import yaml
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import partial

# lightrag-hku 官方导入
try:
    from lightrag import LightRAG, QueryParam
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed
    from lightrag.utils import EmbeddingFunc
    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAG = None
    QueryParam = None
    openai_complete_if_cache = None
    openai_embed = None
    EmbeddingFunc = None

# 导入项目配置
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings


class LightRAGWrapper:
    """
    LightRAG 包装类
    
    与 PageIndexWrapper 保持一致的接口风格，便于 GlobalSearchService 统一调用。
    
    位置：lib/lightrag/wrapper.py
    导出：lib/lightrag/__init__.py
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        if not LIGHTRAG_AVAILABLE:
            raise ImportError(
                "lightrag-hku is not installed. "
                "Install it with: pip install lightrag-hku>=1.4.10"
            )
        
        # 加载配置 - 优先使用传入的路径，否则使用默认路径
        if config_path is None:
            # 默认配置位于模块目录下
            config_path = Path(__file__).parent / "config.yaml"
        
        # 如果模块目录没有，尝试项目根目录的 config/
        if not config_path.exists():
            config_path = Path("config/lightrag_config.yaml")
        
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # 存储 working_dir 路径
        self.working_dir = Path(self.config["storage"]["working_dir"])
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
        # LightRAG 实例（延迟初始化）
        self._rag: Optional[LightRAG] = None
    
    async def initialize(self):
        """
        初始化 LightRAG 实例
        
        注意：必须先调用此方法才能使用其他功能
        """
        if self._rag is not None:
            return
        
        # 构建 LLM 函数（复用项目配置）
        llm_model_func = partial(
            openai_complete_if_cache,
            model=self.config["llm"]["model"],
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            max_tokens=self.config["llm"]["max_tokens"],
            temperature=self.config["llm"]["temperature"],
        )
        
        # 构建嵌入函数（复用项目配置）
        embedding_func = EmbeddingFunc(
            embedding_dim=self.config["embedding"]["dimensions"],
            max_token_size=self.config["embedding"]["max_token_size"],
            func=partial(
                openai_embed,
                model=self.config["embedding"]["model"],
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            ),
        )
        
        # 创建 LightRAG 实例（使用官方 API）
        self._rag = LightRAG(
            working_dir=str(self.working_dir),
            llm_model_func=llm_model_func,
            llm_model_max_async=self.config["llm"]["max_async_calls"],
            embedding_func=embedding_func,
            # 分块配置
            chunk_token_size=self.config["chunking"]["chunk_token_size"],
            chunk_overlap_token_size=self.config["chunking"]["chunk_overlap_token_size"],
            # 存储配置
            kv_storage=self.config["storage"]["kv_storage"],
            vector_storage=self.config["storage"]["vector_storage"],
            graph_storage=self.config["storage"]["graph_storage"],
            doc_status_storage=self.config["storage"]["doc_status_storage"],
        )
        
        # 关键：初始化存储（官方要求）
        await self._rag.initialize_storages()
        
        print(f"[LightRAGWrapper] Initialized with working_dir: {self.working_dir}")
    
    async def index_document(
        self,
        document_id: str,
        text: str,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        为文档构建 LightRAG 索引
        
        lightrag-hku 自动处理：
        - 文本分块
        - 实体提取
        - 关系抽取
        - 图构建
        - 社区检测
        - 向量化存储
        
        Args:
            document_id: 文档唯一标识
            text: 文档文本内容
            file_path: 文件路径（可选，用于溯源）
        
        Returns:
            索引统计信息
        """
        if not self._rag:
            raise RuntimeError("LightRAG not initialized. Call initialize() first.")
        
        print(f"[LightRAGWrapper] Indexing document: {document_id}")
        
        # 使用 lightrag-hku 的异步插入 API
        # 注意：lightrag-hku 支持通过 ids 参数指定文档 ID
        await self._rag.ainsert(text, ids=[document_id])
        
        # 返回统计信息（lightrag-hku 不直接提供，我们简单返回）
        return {
            "document_id": document_id,
            "status": "completed",
            "working_dir": str(self.working_dir),
        }
    
    async def search(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行检索
        
        lightrag-hku 自动处理：
        - Query 分析
        - Low-level 检索（实体级别）
        - High-level 检索（社区级别）
        - 上下文聚合
        - 答案生成
        
        Args:
            query: 查询问题
            mode: 检索模式 (local/global/hybrid/naive/mix)
            top_k: 检索数量限制（可选）
        
        Returns:
            {
                "answer": str,           # 生成的答案
                "query": str,            # 原始查询
                "mode": str,             # 使用的检索模式
                "working_dir": str,      # 工作目录
            }
        """
        if not self._rag:
            raise RuntimeError("LightRAG not initialized. Call initialize() first.")
        
        # 构建 QueryParam
        param = QueryParam(
            mode=mode,
            top_k=top_k or self.config["retrieval"]["top_k"],
            # 可以添加其他参数，如 only_need_context 等
        )
        
        # 执行查询
        result = await self._rag.aquery(query, param=param)
        
        return {
            "answer": result,
            "query": query,
            "mode": mode,
            "working_dir": str(self.working_dir),
        }
    
    async def search_multi(
        self,
        queries: List[str],
        mode: str = "hybrid"
    ) -> List[Dict[str, Any]]:
        """
        批量执行多个查询
        
        注意：lightrag-hku 原生支持多文档存储在同一个 working_dir 中，
        因此 "多文档搜索" 实际上是调用 search() 多次或使用批量查询
        
        Args:
            queries: 查询列表
            mode: 检索模式
        
        Returns:
            结果列表
        """
        tasks = [self.search(q, mode=mode) for q in queries]
        return await asyncio.gather(*tasks)
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息
        
        注意：lightrag-hku 的统计信息需要从存储中读取
        """
        if not self._rag:
            return {"status": "not_initialized"}
        
        # 从 doc_status 存储获取文档数量
        # 注意：这部分依赖于 lightrag-hku 的内部实现，可能需要调整
        return {
            "working_dir": str(self.working_dir),
            "status": "initialized",
            # 其他统计信息可以从存储目录的文件中推断
        }
    
    async def delete_document(self, document_id: str) -> bool:
        """
        删除文档
        
        lightrag-hku v1.4.10 支持通过 adelete_by_doc_id 删除文档
        """
        if not self._rag:
            raise RuntimeError("LightRAG not initialized. Call initialize() first.")
        
        try:
            await self._rag.adelete_by_doc_id(document_id)
            return True
        except Exception as e:
            print(f"[LightRAGWrapper] Error deleting document {document_id}: {e}")
            return False
    
    async def close(self):
        """关闭资源"""
        if self._rag:
            await self._rag.finalize_storages()
            self._rag = None
