# lib/hirag_wrapper/wrapper.py

"""HiRAG 包装层 — 层次化分块 (S8 Hierarchical Chunking).

对应 Weaviate 文章中 S8 Hierarchical Chunking 的深度实现：
与 PageIndex 基于文档显式结构（标题/目录）构建层次不同，
HiRAG 通过 GMM 聚类自动发现内容中的隐含层次结构。

三层检索（chunk → community → global）是 S8 多粒度检索能力的体现——
在不同层级获取不同粒度的信息。

适用场景：复杂关系分析、层次化知识检索、无明确标题结构的文档
策略详情：docs/chunking_strategy_mapping.md#33-hirag

职责：
1. 适配 HiRAG API 到项目统一接口
2. 配置管理（从 YAML 读取配置，传递给 HiRAG）
3. 多文档查询封装（HiRAG 原生支持单 workspace 多文档）
4. 统计信息获取（用于监控和调试）

注意：
- 所有核心功能（分块、实体提取、图构建、层次化聚类）都由 HiRAG 提供
- 本模块只提供包装和配置，不实现核心算法

References:
    - Paper: https://arxiv.org/abs/2503.10150
    - GitHub: https://github.com/hhy-huang/HiRAG
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# HiRAG 官方导入
try:
    from hirag import HiRAG, QueryParam
    from hirag._storage import NetworkXStorage

    HIRAG_AVAILABLE = True
except ImportError:
    HIRAG_AVAILABLE = False
    HiRAG = None
    QueryParam = None
    NetworkXStorage = None

# OpenAI 导入
try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

# 导入项目配置
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings


@dataclass
class EmbeddingFunc:
    """Embedding 函数包装类."""

    embedding_dim: int
    max_token_size: int
    func: callable

    async def __call__(self, *args, **kwargs) -> np.ndarray:
        """调用嵌入函数."""
        return await self.func(*args, **kwargs)


def wrap_embedding_func_with_attrs(**kwargs):
    """Wrap a function with attributes."""

    def final_decorator(func) -> EmbeddingFunc:
        return EmbeddingFunc(**kwargs, func=func)

    return final_decorator


class HiRAGWrapper:
    """HiRAG 包装类.

    与 PageIndexWrapper、LightRAGWrapper 保持一致的接口风格，
    便于 GlobalSearchService 统一调用。

    位置：lib/hirag_wrapper/wrapper.py
    导出：lib/hirag_wrapper/__init__.py
    """

    def __init__(self, config_path: Path | None = None):
        """Initialize HiRAG wrapper.

        Args:
            config_path: 配置文件路径，默认使用模块目录下的 config.yaml
        """
        if not HIRAG_AVAILABLE:
            raise ImportError(
                "HiRAG is not installed. Install it with: cd lib/hirag && pip install -e ."
            )

        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI is required for HiRAG")

        # 加载配置 - 使用模块目录下的 config.yaml
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"HiRAG config not found: {config_path}")

        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # 存储 working_dir 路径
        self.working_dir = Path(self.config["storage"]["working_dir"])
        self.working_dir.mkdir(parents=True, exist_ok=True)

        # HiRAG 实例（延迟初始化）
        self._rag: HiRAG | None = None

        # OpenAI 客户端
        self._openai_client: AsyncOpenAI | None = None

    def _get_openai_client(self) -> AsyncOpenAI:
        """获取或创建 OpenAI 客户端."""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        return self._openai_client

    @wrap_embedding_func_with_attrs(
        embedding_dim=3072,  # text-embedding-3-large
        max_token_size=8192,
    )
    async def _embedding_func(self, texts: list[str]) -> np.ndarray:
        """Embedding 函数."""
        client = self._get_openai_client()
        response = await client.embeddings.create(
            model=self.config["embedding"]["model"],
            input=texts,
            encoding_format="float",
        )
        return np.array([dp.embedding for dp in response.data])

    async def _llm_model_func(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list | None = None,
        **kwargs,
    ) -> str:
        """LLM 调用函数."""
        client = self._get_openai_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=self.config["llm"]["model"],
            messages=messages,
            temperature=self.config["llm"].get("temperature", 0.0),
            max_tokens=self.config["llm"].get("max_tokens", 4000),
        )
        return response.choices[0].message.content

    async def initialize(self):
        """初始化 HiRAG 实例.

        注意：必须先调用此方法才能使用其他功能
        """
        if self._rag is not None:
            return

        # 构建 embedding 函数
        embedding_func = EmbeddingFunc(
            embedding_dim=self.config["embedding"]["dimensions"],
            max_token_size=self.config["embedding"]["max_token_size"],
            func=self._embedding_func,
        )

        # 创建 HiRAG 实例
        self._rag = HiRAG(
            working_dir=str(self.working_dir),
            enable_llm_cache=self.config.get("enable_llm_cache", True),
            embedding_func=embedding_func,
            best_model_func=self._llm_model_func,
            cheap_model_func=self._llm_model_func,
            enable_hierachical_mode=self.config.get("enable_hierarchical", True),
            embedding_batch_num=self.config.get("embedding_batch_num", 6),
            embedding_func_max_async=self.config.get("embedding_func_max_async", 8),
            enable_naive_rag=self.config.get("enable_naive_rag", True),
            graph_storage_cls=NetworkXStorage,
        )

        print(f"[HiRAGWrapper] Initialized with working_dir: {self.working_dir}")

    async def index_document(
        self,
        document_id: str,
        text: str,
        file_path: str | None = None,
    ) -> dict[str, Any]:
        """为文档构建 HiRAG 索引.

        HiRAG 自动处理：
        - 文本分块
        - 实体提取
        - 关系抽取
        - 图构建
        - 层次化聚类（GMM）
        - 社区检测

        Args:
            document_id: 文档唯一标识
            text: 文档文本内容
            file_path: 文件路径（可选，用于溯源）

        Returns:
            索引统计信息
        """
        if not self._rag:
            raise RuntimeError("HiRAG not initialized. Call initialize() first.")

        print(f"[HiRAGWrapper] Indexing document: {document_id}")

        # 使用 HiRAG 的 insert 方法索引文档
        # 注意：HiRAG 目前不直接支持 ids 参数，我们使用 doc_id 作为命名空间
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._rag.insert, text)

        return {
            "document_id": document_id,
            "status": "completed",
            "working_dir": str(self.working_dir),
        }

    async def search(
        self,
        query: str,
        mode: str = "hi",
        top_k: int | None = None,
    ) -> dict[str, Any]:
        """执行检索.

        HiRAG 自动处理：
        - Query 分析
        - Local 检索（实体级别）
        - Global 检索（社区级别）
        - Bridge 检索（连接路径）
        - 上下文聚合
        - 答案生成

        Args:
            query: 查询问题
            mode: 检索模式
                - "hi": 完整 HiRAG 检索（local + global + bridge）
                - "naive": 基础向量检索
                - "hi_nobridge": 不使用 bridge 路径
                - "hi_local": 仅 local 检索
                - "hi_global": 仅 global 检索
                - "hi_bridge": 仅 bridge 检索
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
            raise RuntimeError("HiRAG not initialized. Call initialize() first.")

        # 构建 QueryParam
        param = QueryParam(mode=mode)

        # 执行查询（HiRAG 的 query 是同步的，在线程池中运行）
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._rag.query, query, param)

        return {
            "answer": result,
            "query": query,
            "mode": mode,
            "working_dir": str(self.working_dir),
        }

    async def search_multi(
        self,
        queries: list[str],
        mode: str = "hi",
    ) -> list[dict[str, Any]]:
        """批量执行多个查询.

        Args:
            queries: 查询列表
            mode: 检索模式

        Returns:
            结果列表
        """
        tasks = [self.search(q, mode=mode) for q in queries]
        return await asyncio.gather(*tasks)

    async def get_stats(self) -> dict[str, Any]:
        """获取索引统计信息.

        Returns:
            统计信息字典
        """
        if not self._rag:
            return {"status": "not_initialized"}

        return {
            "working_dir": str(self.working_dir),
            "status": "initialized",
        }

    async def close(self):
        """关闭资源."""
        self._rag = None
        self._openai_client = None
