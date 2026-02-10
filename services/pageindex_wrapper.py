"""
PageIndex 包装层

根据实际 API 探索结果实现的包装层。
参考文档：docs/pageindex_api_exploration.md
"""
import yaml
import asyncio
from pathlib import Path
from typing import Dict, Any
from functools import partial
from config import settings


class PageIndexWrapper:
    """PageIndex 核心函数的包装层"""

    def __init__(self):
        # 加载 PageIndex 配置
        config_path = Path("config/pageindex_config.yaml")
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # 设置 API 配置（注意：这些不会传递给 PageIndex）
        # PageIndex 会从环境变量或其他方式读取 API key
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = self.config.get("model", settings.openai_model)

    async def build_tree_from_pdf(
        self,
        pdf_path: str,
        storage_dir: Path
    ) -> Dict[str, Any]:
        """
        使用 PageIndex 处理 PDF

        Args:
            pdf_path: PDF 文件路径
            storage_dir: 存储目录（用于保存中间结果）

        Returns:
            树结构字典，格式：{"nodes": [...]}
        """
        from pageindex.page_index import page_index

        # page_index 是同步函数，内部使用 asyncio.run()
        # 在 async 上下文中需要在线程池中运行，避免事件循环冲突
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,  # 使用默认执行器
            partial(
                page_index,
                doc=pdf_path,
                model=self.model,
                toc_check_page_num=self.config.get("toc_check_page_num", 20),
                max_page_num_each_node=self.config.get("max_page_num_each_node", 10),
                max_token_num_each_node=self.config.get("max_token_num_each_node", 20000),
                if_add_node_id=self.config.get("if_add_node_id", "yes"),
                if_add_node_summary=self.config.get("if_add_node_summary", "yes"),
                if_add_doc_description=self.config.get("if_add_doc_description", "yes"),
                if_add_node_text=self.config.get("if_add_node_text", "no")
            )
        )

        # 转换为我们的 API 格式
        return self._normalize_result(result)

    async def build_tree_from_markdown(
        self,
        md_path: str,
        storage_dir: Path
    ) -> Dict[str, Any]:
        """
        使用 PageIndex 处理 Markdown

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
            if_add_node_summary=self.config.get("if_add_node_summary", "yes"),
            summary_token_threshold=self.config.get("max_token_num_each_node", 20000),
            model=self.model,
            if_add_doc_description=self.config.get("if_add_doc_description", "yes"),
            if_add_node_text=self.config.get("if_add_node_text", "no"),
            if_add_node_id=self.config.get("if_add_node_id", "yes")
        )

        # 转换为我们的 API 格式
        return self._normalize_result(result)

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 PageIndex 输出转换为我们的标准格式

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
            'doc_name': result.get('doc_name', 'unknown'),
            'nodes': result.get('structure', [])
        }

        # 如果有文档描述，也包含进来
        if 'doc_description' in result:
            normalized['doc_description'] = result['doc_description']

        return normalized
