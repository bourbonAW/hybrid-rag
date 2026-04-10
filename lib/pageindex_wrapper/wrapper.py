"""PageIndex 包装层 — 文档结构分块 (S3) + LLM 分块 (S5) + 层次化分块 (S8).

本模块对应 Weaviate 文章中 3 种分块策略的融合实现：
- S3 Document-Based Chunking: 按 PDF 页面布局 / Markdown 标题层级切分
- S5 LLM-Based Chunking: VLM/LLM 直接分析文档结构生成树节点
- S8 Hierarchical Chunking: 输出多层级树结构，支持渐进式检索

适用场景：长文档深度分析、单文档精读、结构化报告
策略详情：docs/chunking_strategy_mapping.md#31-pageindex

根据实际 API 探索结果实现的包装层。
参考文档：docs/pageindex_api_exploration.md
"""

import asyncio
from functools import partial
from pathlib import Path
from typing import Any

from config import settings


class PageIndexWrapper:
    """PageIndex 核心函数的包装层."""

    def __init__(self):
        """Initialize PageIndex wrapper."""
        # PageIndex 配置（直接硬编码，简化管理）
        self.config = {
            "model": settings.openai_model,  # 使用全局模型配置
            "toc_check_page_num": 20,
            "max_page_num_each_node": 10,
            "max_token_num_each_node": 20000,
            "if_add_node_id": "yes",
            "if_add_node_summary": "yes",
            "if_add_doc_description": "yes",
            "if_add_node_text": "no",
        }

        # 设置 API 配置（注意：这些不会传递给 PageIndex）
        # PageIndex 会从环境变量或其他方式读取 API key
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = self.config["model"]

    async def build_tree_from_pdf(self, pdf_path: str, storage_dir: Path) -> dict[str, Any]:
        """使用 PageIndex 处理 PDF — S3 文档结构分块 + S5 LLM 分块.

        VLM 分析 PDF 页面图像，识别文档结构（目录、标题、段落），
        生成层次化树索引。这是文章中 S5 LLM-Based Chunking 的视觉模态实现。

        Args:
            pdf_path: PDF 文件路径
            storage_dir: 存储目录（用于保存中间结果）

        Returns:
            树结构字典，格式：{"nodes": [...]}
        """
        from pageindex.page_index import page_index

        # page_index 是同步函数，内部使用 asyncio.run()
        # 在 async 上下文中需要在线程池中运行，避免事件循环冲突
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,  # 使用默认执行器
            partial(
                page_index,
                doc=pdf_path,
                model=self.model,
                toc_check_page_num=self.config["toc_check_page_num"],
                max_page_num_each_node=self.config["max_page_num_each_node"],
                max_token_num_each_node=self.config["max_token_num_each_node"],
                if_add_node_id=self.config["if_add_node_id"],
                if_add_node_summary=self.config["if_add_node_summary"],
                if_add_doc_description=self.config["if_add_doc_description"],
                if_add_node_text=self.config["if_add_node_text"],
            ),
        )

        # 转换为我们的 API 格式
        return self._normalize_result(result)

    async def build_tree_from_markdown(self, md_path: str, storage_dir: Path) -> dict[str, Any]:
        """使用 PageIndex 处理 Markdown — S3 文档结构分块 + S8 层次化分块.

        按 Markdown 标题层级（#, ##, ###）构建多层树结构。
        这是文章中 S3 Document-Based Chunking 最直接的实现——
        Markdown 的标题就是天然的语义边界。

        Args:
            md_path: Markdown 文件路径
            storage_dir: 存储目录

        Returns:
            树结构字典，格式：{"nodes": [...]}
        """
        from pageindex.page_index_md import md_to_tree

        # 调用 PageIndex 核心函数
        # 注意：md_to_tree 是异步函数，需要 await
        result = await md_to_tree(
            md_path=md_path,
            if_thinning=False,
            if_add_node_summary=self.config["if_add_node_summary"],
            summary_token_threshold=self.config["max_token_num_each_node"],
            model=self.model,
            if_add_doc_description=self.config["if_add_doc_description"],
            if_add_node_text=self.config["if_add_node_text"],
            if_add_node_id=self.config["if_add_node_id"],
        )

        # 转换为我们的 API 格式
        return self._normalize_result(result)

    def _normalize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """将 PageIndex 输出转换为我们的标准格式.

        PageIndex 输出格式：
        {
            'doc_name': str,
            'doc_description': str,  # 可选
            'structure': [...]       # 树结构列表
        }

        我们的格式：
        {
            'doc_name': str,
            'doc_description': str,  # 可选
            'nodes': [...]           # 包装后的树结构
        }
        """
        # PageIndex 返回的 structure 就是节点列表，只需要重命名键
        normalized = {
            "doc_name": result.get("doc_name", "unknown"),
            "nodes": result.get("structure", []),
        }

        # 如果有文档描述，也包含进来
        if "doc_description" in result:
            normalized["doc_description"] = result["doc_description"]

        return normalized
