import time
from pathlib import Path
from typing import Any

from models.schemas import SearchResponse, SearchResult
from services.legacy.llm_client import LLMClient


class SearchService:
    """Document search service."""

    def __init__(self, vlm: Any | None, llm: LLMClient):
        """Initialize search service."""
        self.vlm = vlm  # 现在不使用，保留参数兼容性
        self.llm = llm

    async def search(
        self, query: str, tree: dict[str, Any], doc_format: str, storage_path: str, top_k: int = 3
    ) -> SearchResponse:
        """Perform reasoning-based search."""
        start_time = time.time()

        # Use LLM for all formats (PageIndex already extracted text content)
        search_result = await self.llm.search_tree(tree, query)

        # Get results based on format
        if doc_format == "pdf":
            results = await self._get_pdf_results(query, search_result, tree, storage_path, top_k)
        else:
            results = await self._get_text_results(query, search_result, tree, storage_path, top_k)

        processing_time = (time.time() - start_time) * 1000

        return SearchResponse(
            query=query,
            results=results,
            total_nodes=len(results),
            processing_time_ms=processing_time,
        )

    async def _get_pdf_results(
        self, query: str, search_result: dict, tree: dict, storage_path: str, top_k: int
    ) -> list[SearchResult]:
        """Get results for PDF (using text content from PageIndex)."""
        node_list = search_result.get("node_list", [])[:top_k]
        thinking = search_result.get("thinking", "")

        results = []
        node_map = self._build_node_map(tree["nodes"])

        for node_id in node_list:
            node = node_map.get(node_id)
            if not node:
                continue

            # Use node content extracted by PageIndex
            # PageIndex uses "summary" field for node summaries
            context = node.get("summary", "") or node.get("content", "") or node.get("text", "")

            # If no content in node, try to load from tree structure
            if not context:
                context = f"Section: {node.get('title', 'Unknown')}"

            # Generate answer using LLM with text content
            answer = await self.llm.answer_with_text(query, context)

            # PageIndex uses "start_index" and "end_index" for page ranges
            page_start = node.get("start_index") or node.get("page_start", 1)
            page_end = node.get("end_index") or node.get("page_end", page_start)

            results.append(
                SearchResult(
                    node_id=node_id,
                    title=node["title"],
                    content=answer,
                    relevance_score=1.0,
                    page_refs=list(range(page_start, page_end + 1)),
                    reasoning_path=[thinking],
                )
            )

        return results

    async def _get_text_results(
        self, query: str, search_result: dict, tree: dict, storage_path: str, top_k: int
    ) -> list[SearchResult]:
        """Get results for text documents."""
        node_list = search_result.get("node_list", [])[:top_k]
        thinking = search_result.get("thinking", "")

        results = []
        node_map = self._build_node_map(tree["nodes"])

        # Load full content
        content_path = Path(storage_path) / "content.txt"
        full_content = ""
        if content_path.exists():
            with open(content_path) as f:
                full_content = f.read()

        for node_id in node_list:
            node = node_map.get(node_id)
            if not node:
                continue

            # Use node content or extract from full content
            context = node.get("content", "") or full_content[:2000]
            answer = await self.llm.answer_with_text(query, context)

            results.append(
                SearchResult(
                    node_id=node_id,
                    title=node["title"],
                    content=answer,
                    relevance_score=1.0,
                    page_refs=[node.get("page_start", 1)],
                    reasoning_path=[thinking],
                )
            )

        return results

    def _build_node_map(self, nodes: list[dict], prefix: str = "") -> dict[str, dict]:
        """Flatten tree to node_id -> node mapping."""
        result = {}
        for node in nodes:
            # PageIndex uses "node_id" as the field name
            node_id = node.get("node_id") or node.get("id")
            if node_id:
                result[node_id] = node
                # Recursively process children nodes
                if "nodes" in node and node["nodes"]:
                    result.update(self._build_node_map(node["nodes"]))
                elif "children" in node and node["children"]:
                    result.update(self._build_node_map(node["children"]))
        return result
