import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from models.schemas import SearchResponse, SearchResult
from services.legacy.llm_client import LLMClient


class SearchService:
    def __init__(self, vlm: Optional[Any], llm: LLMClient):
        self.vlm = vlm  # 现在不使用，保留参数兼容性
        self.llm = llm

    async def search(
        self,
        query: str,
        tree: Dict[str, Any],
        doc_format: str,
        storage_path: str,
        top_k: int = 3
    ) -> SearchResponse:
        """Perform reasoning-based search."""
        start_time = time.time()

        # Use VLM for PDF, LLM for text formats
        if doc_format == "pdf":
            search_result = await self.vlm.search_tree(tree, query)
            results = await self._get_pdf_results(
                query, search_result, tree, storage_path, top_k
            )
        else:
            search_result = await self.llm.search_tree(tree, query)
            results = await self._get_text_results(
                query, search_result, tree, storage_path, top_k
            )

        processing_time = (time.time() - start_time) * 1000

        return SearchResponse(
            query=query,
            results=results,
            total_nodes=len(results),
            processing_time_ms=processing_time
        )

    async def _get_pdf_results(
        self,
        query: str,
        search_result: Dict,
        tree: Dict,
        storage_path: str,
        top_k: int
    ) -> List[SearchResult]:
        """Get results for PDF (with page images)."""
        node_list = search_result.get("node_list", [])[:top_k]
        thinking = search_result.get("thinking", "")

        results = []
        node_map = self._build_node_map(tree["nodes"])

        for node_id in node_list:
            node = node_map.get(node_id)
            if not node:
                continue

            # Get page images for this node
            page_images = []
            pages_dir = Path(storage_path) / "pages"
            for page_num in range(node["page_start"], node["page_end"] + 1):
                img_path = pages_dir / f"page_{page_num:04d}.jpg"
                if img_path.exists():
                    page_images.append(str(img_path))

            # Generate answer using VLM with images
            if page_images:
                answer = await self.vlm.answer_with_images(query, page_images)
            else:
                answer = "No visual content available"

            results.append(SearchResult(
                node_id=node_id,
                title=node["title"],
                content=answer,
                relevance_score=1.0,
                page_refs=list(range(node["page_start"], node["page_end"] + 1)),
                reasoning_path=[thinking]
            ))

        return results

    async def _get_text_results(
        self,
        query: str,
        search_result: Dict,
        tree: Dict,
        storage_path: str,
        top_k: int
    ) -> List[SearchResult]:
        """Get results for text documents."""
        node_list = search_result.get("node_list", [])[:top_k]
        thinking = search_result.get("thinking", "")

        results = []
        node_map = self._build_node_map(tree["nodes"])

        # Load full content
        content_path = Path(storage_path) / "content.txt"
        full_content = ""
        if content_path.exists():
            with open(content_path, "r") as f:
                full_content = f.read()

        for node_id in node_list:
            node = node_map.get(node_id)
            if not node:
                continue

            # Use node content or extract from full content
            context = node.get("content", "") or full_content[:2000]
            answer = await self.llm.answer_with_text(query, context)

            results.append(SearchResult(
                node_id=node_id,
                title=node["title"],
                content=answer,
                relevance_score=1.0,
                page_refs=[node.get("page_start", 1)],
                reasoning_path=[thinking]
            ))

        return results

    def _build_node_map(self, nodes: List[Dict], prefix: str = "") -> Dict[str, Dict]:
        """Flatten tree to node_id -> node mapping."""
        result = {}
        for node in nodes:
            node_id = node["id"]
            result[node_id] = node
            if "children" in node and node["children"]:
                result.update(self._build_node_map(node["children"]))
        return result
