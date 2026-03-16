import asyncio
import time
from typing import Any, Optional

from models.document_store import DocumentStore
from services.document_service import DocumentService
from services.legacy.llm_client import LLMClient
from services.search_service import SearchService

# Import LightRAG wrapper
try:
    from lib.lightrag import LightRAGWrapper

    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAGWrapper = None

# Import HiRAG wrapper
try:
    from lib.hirag_wrapper import HiRAGWrapper

    HIRAG_AVAILABLE = True
except ImportError:
    HIRAG_AVAILABLE = False
    HiRAGWrapper = None

# Import Hybrid Search wrapper
try:
    from lib.hybrid_search import HybridSearchWrapper

    HYBRID_SEARCH_AVAILABLE = True
except ImportError:
    HYBRID_SEARCH_AVAILABLE = False
    HybridSearchWrapper = None


class DocumentCandidate:
    """文档候选结果."""

    def __init__(
        self, doc_id: str, filename: str, format: str, relevance_score: float, reasoning: str
    ):
        """Initialize document candidate."""
        self.doc_id = doc_id
        self.filename = filename
        self.format = format
        self.relevance_score = relevance_score
        self.reasoning = reasoning


class GlobalSearchResult:
    """全局搜索结果."""

    def __init__(
        self,
        query: str,
        final_answer: str,
        sources: list[dict[str, Any]],
        document_selection_reasoning: str,
        total_documents_searched: int,
        processing_time_ms: float,
        strategy_used: dict[str, str] | None = None,
        fallback_reasons: list[str] | None = None,
    ):
        """Initialize global search result."""
        self.query = query
        self.final_answer = final_answer
        self.sources = sources
        self.document_selection_reasoning = document_selection_reasoning
        self.total_documents_searched = total_documents_searched
        self.processing_time_ms = processing_time_ms
        self.strategy_used = strategy_used or {}
        self.fallback_reasons = fallback_reasons or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "final_answer": self.final_answer,
            "sources": self.sources,
            "document_selection_reasoning": self.document_selection_reasoning,
            "total_documents_searched": self.total_documents_searched,
            "processing_time_ms": self.processing_time_ms,
            "strategy_used": self.strategy_used,
            "fallback_reasons": self.fallback_reasons,
        }


class GlobalSearchService:
    """全局多文档搜索服务 - 支持 LightRAG 策略."""

    def __init__(
        self,
        doc_store: DocumentStore,
        doc_service: DocumentService,
        search_service: SearchService,
        llm: LLMClient,
        lightrag_wrapper: Optional["LightRAGWrapper"] = None,
        hirag_wrapper: Optional["HiRAGWrapper"] = None,
        hybrid_search_wrapper: Optional["HybridSearchWrapper"] = None,
    ):
        """Initialize global search service."""
        self.doc_store = doc_store
        self.doc_service = doc_service
        self.search_service = search_service
        self.llm = llm
        self.lightrag = lightrag_wrapper
        self.hirag = hirag_wrapper
        self.hybrid_search = hybrid_search_wrapper

    async def search(
        self,
        query: str,
        top_k_documents: int = 3,
        top_k_results_per_doc: int = 2,
        strategy: str = "auto",  # 新增: "pageindex", "lightrag", "hirag", "hybrid", "auto"
    ) -> GlobalSearchResult:
        """执行全局多文档搜索.

        Args:
            query: 用户问题
            top_k_documents: 选择最相关的文档数量
            top_k_results_per_doc: 每个文档返回的结果数量
            strategy:
                - "pageindex": 仅使用 PageIndex（原有逻辑）
                - "lightrag": 仅使用 LightRAG
                - "hybrid": LightRAG 粗筛 + PageIndex 精读（推荐）
                - "auto": 自动选择（默认）
        """
        # 自动选择策略
        if strategy == "auto":
            strategy = self._select_strategy(query)

        # Execute search with selected strategy
        if strategy == "pageindex":
            return await self._search_pageindex(query, top_k_documents, top_k_results_per_doc)
        elif strategy == "lightrag":
            return await self._search_lightrag(query)
        elif strategy == "hirag":
            return await self._search_hirag(query)
        elif strategy == "hybrid_search":
            return await self._search_hybrid_search(query, top_k_documents, top_k_results_per_doc)
        else:  # hybrid
            return await self._search_hybrid(query, top_k_documents, top_k_results_per_doc)

    async def _select_documents(self, query: str, top_k: int) -> list[DocumentCandidate]:
        """阶段1: 基于 LLM 推理选择相关文档."""
        # 获取所有已完成的文档（使用新的 SQLite 存储 API）
        all_documents = []
        completed_docs = await self.doc_store.list_completed_documents()

        for doc in completed_docs:
            # 获取文档树结构作为摘要
            tree = self.doc_service.get_tree(doc.id)
            if tree:
                # 提取文档的顶层标题和内容作为摘要
                summary = self._extract_document_summary(tree)
                all_documents.append(
                    {
                        "doc_id": doc.id,
                        "filename": doc.filename,
                        "format": doc.format,
                        "summary": summary,
                    }
                )

        if not all_documents:
            return []

        print(f"[GlobalSearch] Found {len(all_documents)} completed documents")
        print("[GlobalSearch] Document summaries prepared, calling LLM for selection...")

        # 用 LLM 分析并选择最相关的文档
        prompt = f"""给定用户问题和文档列表，选择最相关的 {top_k} 个文档。

用户问题：{query}

可用文档：
{self._format_documents_for_llm(all_documents)}

请分析每个文档与问题的相关性，返回 JSON 格式：
{{
  "thinking": "你对文档相关性的分析推理过程",
  "selected_documents": [
    {{
      "doc_id": "文档ID",
      "relevance_score": 0.95,
      "reasoning": "选择该文档的理由"
    }}
  ]
}}

只返回 JSON，不要其他文字。最多返回 {top_k} 个文档。"""

        try:
            print(
                f"[GlobalSearch] Calling LLM API: {self.llm.client.base_url} with model {self.llm.model}"
            )
            response = await asyncio.wait_for(
                self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=2000,
                    timeout=60.0,
                ),
                timeout=120.0,
            )
            print("[GlobalSearch] LLM response received")
        except TimeoutError:
            print("[GlobalSearch] ERROR: LLM API call timed out after 120 seconds")
            raise Exception("LLM API 调用超时，请检查网络连接和 API 配置") from None
        except Exception as e:
            print(f"[GlobalSearch] ERROR: LLM API call failed: {e}")
            raise

        result_text = response.choices[0].message.content
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        import json

        selection_result = json.loads(result_text.strip())

        # 构建候选文档列表
        candidates = []
        doc_map = {d["doc_id"]: d for d in all_documents}

        for selected in selection_result.get("selected_documents", [])[:top_k]:
            doc_info = doc_map.get(selected["doc_id"])
            if doc_info:
                candidates.append(
                    DocumentCandidate(
                        doc_id=selected["doc_id"],
                        filename=doc_info["filename"],
                        format=doc_info["format"],
                        relevance_score=selected.get("relevance_score", 0.0),
                        reasoning=selected.get("reasoning", ""),
                    )
                )

        return candidates

    def _select_strategy(self, query: str) -> str:
        """自动选择最优策略.

        启发式规则：
        - 关键词导向查询（代码、ID、术语）→ hybrid_search (BM25+Vector)
        - 短查询、事实性问题 → LightRAG (fast)
        - 层次化、关系复杂查询 → HiRAG (hierarchical)
        - 长查询、需要深度分析 → PageIndex (deep)
        - 跨文档比较 → Hybrid
        """
        # 关键词导向查询 → Hybrid Search (BM25 精确匹配)
        if HYBRID_SEARCH_AVAILABLE and self.hybrid_search and self._is_keyword_query(query):
            return "hybrid_search"

        # 层次化、关系复杂查询 → HiRAG
        if HIRAG_AVAILABLE and self.hirag and any(
            kw in query for kw in ["层次", "结构", "关系", "关联", "层次化"]
        ):
            return "hirag"

        if not LIGHTRAG_AVAILABLE or not self.lightrag:
            return "pageindex"

        if len(query) < 20:
            return "lightrag"
        elif "比较" in query or "对比" in query or "difference" in query.lower():
            return "hybrid"
        else:
            return "hybrid_search" if HYBRID_SEARCH_AVAILABLE and self.hybrid_search else "hybrid"

    def _is_keyword_query(self, query: str) -> bool:
        """判断是否为关键词导向的查询.

        关键词导向查询通常包含：
        - 代码片段 (function, class, def, api, endpoint)
        - ID/编号 (id:, 编号, #)
        - 精确术语 (带引号的短语)
        """
        query_lower = query.lower()
        keyword_indicators = [
            # 代码/技术术语
            "function",
            "class",
            "def ",
            "api",
            "endpoint",
            "method",
            # ID/编号
            "id:",
            "编号",
            "代码",
            # 精确匹配
            '"',
            "'",
        ]
        return any(ind in query_lower for ind in keyword_indicators)

    async def _search_pageindex(
        self, query: str, top_k_documents: int, top_k_results_per_doc: int
    ) -> GlobalSearchResult:
        """纯 PageIndex 搜索（原有逻辑）.

        适用于：深度分析、单文档精读
        """
        start_time = time.time()
        print("[GlobalSearch] Using PageIndex strategy")

        # 阶段1: 文档选择（检查索引可用性）
        print("[GlobalSearch] Phase 1: Document Selection")
        candidates = await self._select_documents(query, top_k_documents)

        # 策略回退：检查每个文档是否有 PageIndex tree
        strategy_map = {}
        fallback_reasons = []
        valid_candidates = []

        for candidate in candidates:
            tree = self.doc_service.get_tree(candidate.doc_id)
            if tree:
                strategy_map[candidate.doc_id] = "pageindex"
                valid_candidates.append(candidate)
            else:
                fallback_reasons.append(
                    f"Document {candidate.doc_id}: PageIndex tree not available"
                )

        print(f"[GlobalSearch] Selected {len(valid_candidates)} documents with PageIndex support")

        if not valid_candidates:
            processing_time = (time.time() - start_time) * 1000
            return GlobalSearchResult(
                query=query,
                final_answer="未找到支持 PageIndex 的文档。",
                sources=[],
                document_selection_reasoning="PageIndex strategy selected but no compatible documents found",
                total_documents_searched=0,
                processing_time_ms=processing_time,
                strategy_used={},
                fallback_reasons=fallback_reasons,
            )

        # 阶段2: 并行检索每个文档
        print("[GlobalSearch] Phase 2: Parallel Retrieval")
        retrieval_results = await self._parallel_retrieval(query, valid_candidates, top_k_results_per_doc)
        print(f"[GlobalSearch] Retrieved results from {len(retrieval_results)} documents")

        # 阶段3: 答案聚合
        print("[GlobalSearch] Phase 3: Answer Synthesis")
        final_answer, sources = await self._synthesize_answer(query, retrieval_results)
        print(f"[GlobalSearch] Final answer synthesized with {len(sources)} sources")

        processing_time = (time.time() - start_time) * 1000

        return GlobalSearchResult(
            query=query,
            final_answer=final_answer,
            sources=sources,
            document_selection_reasoning=candidates[0].reasoning if candidates else "",
            total_documents_searched=len(valid_candidates),
            processing_time_ms=processing_time,
            strategy_used=strategy_map,
            fallback_reasons=fallback_reasons,
        )

    async def _search_lightrag(self, query: str) -> GlobalSearchResult:
        """纯 LightRAG 搜索.

        适用于：快速事实检索、多文档概览
        """
        if not self.lightrag:
            raise ValueError("LightRAG not configured")

        start_time = time.time()
        print("[GlobalSearch] Using LightRAG strategy")

        # 直接调用 LightRAG（它已经处理了所有文档的索引）
        result = await self.lightrag.search(query, mode="hybrid")

        processing_time = (time.time() - start_time) * 1000

        return GlobalSearchResult(
            query=query,
            final_answer=result["answer"],
            sources=[],  # LightRAG 返回的答案已包含引用
            document_selection_reasoning="LightRAG hybrid search across all indexed documents",
            total_documents_searched=1,  # LightRAG 使用统一索引
            processing_time_ms=processing_time,
            strategy_used={"global": "lightrag"},
            fallback_reasons=[],
        )

    async def _search_hirag(self, query: str) -> GlobalSearchResult:
        """纯 HiRAG 搜索.

        适用于：层次化知识检索、复杂关系分析
        """
        if not self.hirag:
            raise ValueError("HiRAG not configured")

        start_time = time.time()
        print("[GlobalSearch] Using HiRAG strategy")

        # 直接调用 HiRAG（它已经处理了所有文档的索引）
        result = await self.hirag.search(query, mode="hi")

        processing_time = (time.time() - start_time) * 1000

        return GlobalSearchResult(
            query=query,
            final_answer=result["answer"],
            sources=[],  # HiRAG 返回的答案已包含引用
            document_selection_reasoning="HiRAG hierarchical search across all indexed documents",
            total_documents_searched=1,  # HiRAG 使用统一索引
            processing_time_ms=processing_time,
            strategy_used={"global": "hirag"},
            fallback_reasons=[],
        )

    async def _search_hybrid_search(
        self, query: str, top_k_documents: int, top_k_results_per_doc: int
    ) -> GlobalSearchResult:
        """Hybrid Search (BM25 + Vector) 搜索.

        适用于：关键词精确匹配、术语检索、代码片段查找
        """
        if not self.hybrid_search:
            raise ValueError("Hybrid Search not configured")

        start_time = time.time()
        print("[GlobalSearch] Using Hybrid Search strategy (BM25 + Vector)")

        # 阶段1: 文档选择（检查索引可用性）
        print("[GlobalSearch] Phase 1: Document Selection with Strategy Check")
        candidates = await self._select_documents(query, top_k_documents)

        # 策略回退：检查每个文档是否有 hybrid_search 索引
        strategy_map = {}
        fallback_reasons = []
        valid_candidates = []

        for candidate in candidates:
            doc = await self.doc_store.get(candidate.doc_id)
            if doc and "hybrid_search" in doc.available_indexes:
                strategy_map[candidate.doc_id] = "hybrid_search"
                valid_candidates.append(candidate)
            else:
                # Skip documents without hybrid_search index
                fallback_reasons.append(
                    f"Document {candidate.doc_id} skipped: hybrid_search index not available"
                )

        if not valid_candidates:
            processing_time = (time.time() - start_time) * 1000
            return GlobalSearchResult(
                query=query,
                final_answer="未找到支持 hybrid_search 的文档。",
                sources=[],
                document_selection_reasoning="Hybrid Search strategy selected but no compatible documents found",
                total_documents_searched=0,
                processing_time_ms=processing_time,
                strategy_used={},
                fallback_reasons=fallback_reasons,
            )

        print(f"[GlobalSearch] Selected {len(valid_candidates)} documents with hybrid_search support")

        # 阶段2: 对每个文档执行 Hybrid Search
        print("[GlobalSearch] Phase 2: Hybrid Search Retrieval")
        all_results = []
        for candidate in valid_candidates:
            try:
                result = await self.hybrid_search.search(
                    query=query,
                    document_id=candidate.doc_id,
                    top_k=top_k_results_per_doc,
                )
                if result.get("results"):
                    all_results.append({
                        "doc_id": candidate.doc_id,
                        "filename": candidate.filename,
                        "chunks": result["results"],
                    })
            except Exception as e:
                print(f"[GlobalSearch] Hybrid search failed for {candidate.doc_id}: {e}")
                fallback_reasons.append(f"Search failed for {candidate.doc_id}: {str(e)}")

        print(f"[GlobalSearch] Retrieved results from {len(all_results)} documents")

        # 阶段3: 答案聚合
        print("[GlobalSearch] Phase 3: Answer Synthesis")
        final_answer, sources = await self._synthesize_hybrid_answer(query, all_results)
        print(f"[GlobalSearch] Final answer synthesized with {len(sources)} sources")

        processing_time = (time.time() - start_time) * 1000

        return GlobalSearchResult(
            query=query,
            final_answer=final_answer,
            sources=sources,
            document_selection_reasoning="Hybrid Search (BM25 + Vector RRF fusion)",
            total_documents_searched=len(valid_candidates),
            processing_time_ms=processing_time,
            strategy_used=strategy_map,
            fallback_reasons=fallback_reasons,
        )

    async def _synthesize_hybrid_answer(
        self, query: str, results: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        """聚合 Hybrid Search 结果，生成最终答案."""
        if not results:
            return "未找到相关信息。", []

        # 构建上下文
        context_parts = []
        sources = []

        for doc_result in results:
            doc_name = doc_result["filename"]
            for chunk in doc_result["chunks"]:
                context_parts.append(
                    f"【来源：{doc_name} - Chunk {chunk['chunk_index']} (分数: {chunk['score']:.3f})】\n"
                    f"{chunk['text']}\n"
                )
                sources.append({
                    "document_id": doc_result["doc_id"],
                    "document_name": doc_name,
                    "chunk_index": chunk["chunk_index"],
                    "score": chunk["score"],
                    "text_preview": chunk["text"][:200] + "...",
                })

        context = "\n\n".join(context_parts)

        # 用 LLM 综合生成答案
        synthesis_prompt = f"""你是一个专业的文档分析助手。基于从多个文档中检索到的信息，综合回答用户的问题。

用户问题：{query}

来自多个文档的相关片段（按相关性排序）：
{context}

请根据以上信息，生成一个完整、准确的答案。要求：
1. 综合多个来源的信息，不要简单罗列
2. 如果信息不足以完全回答问题，请说明
3. 保持专业和客观的语气

请直接给出答案，不要额外的解释。"""

        try:
            print("[GlobalSearch] Calling LLM for answer synthesis...")
            response = await asyncio.wait_for(
                self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=[{"role": "user", "content": synthesis_prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                    timeout=60.0,
                ),
                timeout=120.0,
            )
            print("[GlobalSearch] Answer synthesis completed")
        except TimeoutError:
            print("[GlobalSearch] ERROR: Answer synthesis timed out")
            return "生成答案时超时，请稍后重试。", sources
        except Exception as e:
            print(f"[GlobalSearch] ERROR: Answer synthesis failed: {e}")
            return f"生成答案时出错：{str(e)}", sources

        final_answer = response.choices[0].message.content
        return final_answer, sources

    async def _search_hybrid(
        self, query: str, top_k_documents: int, top_k_results_per_doc: int
    ) -> GlobalSearchResult:
        """混合搜索：LightRAG 快速筛选 + PageIndex 深度精读.

        策略：
        1. 使用 LightRAG 快速获取相关文档和段落
        2. 对这些文档使用 PageIndex 进行深度树检索
        3. 综合生成答案

        当前简化版：直接使用 LightRAG 结果
        """
        # 当前简化：直接返回 LightRAG 结果
        # TODO: 实现更精细的 hybrid 逻辑
        result = await self._search_lightrag(query)
        # Add strategy info
        result.strategy_used = {"global": "hybrid"}
        result.fallback_reasons = []
        return result

    async def _parallel_retrieval(
        self, query: str, candidates: list[DocumentCandidate], top_k_per_doc: int
    ) -> list[dict[str, Any]]:
        """阶段2: 并行检索每个候选文档."""
        tasks = []
        for candidate in candidates:
            task = self._retrieve_from_document(query, candidate, top_k_per_doc)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤异常结果
        valid_results = []
        for result in results:
            if not isinstance(result, Exception) and result is not None:
                valid_results.append(result)

        return valid_results

    async def _retrieve_from_document(
        self, query: str, candidate: DocumentCandidate, top_k: int
    ) -> dict[str, Any] | None:
        """从单个文档中检索相关内容."""
        try:
            tree = self.doc_service.get_tree(candidate.doc_id)
            if not tree:
                return None

            storage_path = f"./storage/{candidate.doc_id}"

            search_response = await self.search_service.search(
                query=query,
                tree=tree,
                doc_format=candidate.format,
                storage_path=storage_path,
                top_k=top_k,
            )

            return {
                "doc_id": candidate.doc_id,
                "filename": candidate.filename,
                "format": candidate.format,
                "relevance_score": candidate.relevance_score,
                "results": [
                    {
                        "node_id": r.node_id,
                        "title": r.title,
                        "content": r.content,
                        "page_refs": r.page_refs,
                        "reasoning_path": r.reasoning_path,
                    }
                    for r in search_response.results
                ],
            }
        except Exception as e:
            print(f"Error retrieving from document {candidate.doc_id}: {e}")
            return None

    async def _synthesize_answer(
        self, query: str, retrieval_results: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        """阶段3: 聚合多个文档的答案片段，生成最终答案."""
        if not retrieval_results:
            return "未找到相关信息。", []

        # 构建上下文：来自多个文档的信息
        context_parts = []
        sources = []

        for doc_result in retrieval_results:
            doc_name = doc_result["filename"]
            for result in doc_result["results"]:
                context_parts.append(
                    f"【来源：{doc_name} - {result['title']} (页码: {', '.join(map(str, result['page_refs']))})】\n"
                    f"{result['content']}\n"
                )
                sources.append(
                    {
                        "document_id": doc_result["doc_id"],
                        "document_name": doc_name,
                        "section_title": result["title"],
                        "page_refs": result["page_refs"],
                        "node_id": result["node_id"],
                    }
                )

        context = "\n\n".join(context_parts)

        # 用 LLM 综合生成最终答案
        synthesis_prompt = f"""你是一个专业的文档分析助手。基于从多个文档中检索到的信息，综合回答用户的问题。

用户问题：{query}

来自多个文档的相关信息：
{context}

请根据以上信息，生成一个完整、准确的答案。要求：
1. 综合多个来源的信息，不要简单罗列
2. 如果不同文档有矛盾信息，请指出
3. 在答案中标注信息来源（文档名和页码）
4. 如果信息不足以完全回答问题，请说明
5. 保持专业和客观的语气

请直接给出答案，不要额外的解释。"""

        try:
            print("[GlobalSearch] Calling LLM for answer synthesis...")
            response = await asyncio.wait_for(
                self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=[{"role": "user", "content": synthesis_prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                    timeout=60.0,
                ),
                timeout=120.0,
            )
            print("[GlobalSearch] Answer synthesis completed")
        except TimeoutError:
            print("[GlobalSearch] ERROR: Answer synthesis timed out")
            return "生成答案时超时，请稍后重试。", sources
        except Exception as e:
            print(f"[GlobalSearch] ERROR: Answer synthesis failed: {e}")
            return f"生成答案时出错：{str(e)}", sources

        final_answer = response.choices[0].message.content

        return final_answer, sources

    def _extract_document_summary(self, tree: dict[str, Any]) -> str:
        """提取文档的摘要信息（顶层节点）."""
        nodes = tree.get("nodes", [])
        if not nodes:
            return "空文档"

        summaries = []
        for node in nodes[:3]:  # 只取前3个顶层节点
            title = node.get("title", "")
            content = node.get("content", "")[:200]  # 限制长度
            summaries.append(f"- {title}: {content}")

        return "\n".join(summaries)

    def _format_documents_for_llm(self, documents: list[dict]) -> str:
        """格式化文档列表供 LLM 分析."""
        formatted = []
        for i, doc in enumerate(documents, 1):
            formatted.append(
                f"{i}. 文档ID: {doc['doc_id']}\n"
                f"   文件名: {doc['filename']}\n"
                f"   格式: {doc['format']}\n"
                f"   摘要:\n{doc['summary']}\n"
            )
        return "\n".join(formatted)
