import time
import asyncio
from typing import List, Dict, Any, Optional
from models.schemas import SearchResult
from models.document_store import DocumentStore
from services.document_service import DocumentService
from services.search_service import SearchService
from services.legacy.llm_client import LLMClient

# Import LightRAG wrapper
try:
    from lib.lightrag import LightRAGWrapper
    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAGWrapper = None


class DocumentCandidate:
    """文档候选结果"""
    def __init__(self, doc_id: str, filename: str, format: str, relevance_score: float, reasoning: str):
        self.doc_id = doc_id
        self.filename = filename
        self.format = format
        self.relevance_score = relevance_score
        self.reasoning = reasoning


class GlobalSearchResult:
    """全局搜索结果"""
    def __init__(
        self,
        query: str,
        final_answer: str,
        sources: List[Dict[str, Any]],
        document_selection_reasoning: str,
        total_documents_searched: int,
        processing_time_ms: float
    ):
        self.query = query
        self.final_answer = final_answer
        self.sources = sources
        self.document_selection_reasoning = document_selection_reasoning
        self.total_documents_searched = total_documents_searched
        self.processing_time_ms = processing_time_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "final_answer": self.final_answer,
            "sources": self.sources,
            "document_selection_reasoning": self.document_selection_reasoning,
            "total_documents_searched": self.total_documents_searched,
            "processing_time_ms": self.processing_time_ms
        }


class GlobalSearchService:
    """全局多文档搜索服务 - 支持 LightRAG 策略"""

    def __init__(
        self,
        doc_store: DocumentStore,
        doc_service: DocumentService,
        search_service: SearchService,
        llm: LLMClient,
        lightrag_wrapper: Optional["LightRAGWrapper"] = None,
    ):
        self.doc_store = doc_store
        self.doc_service = doc_service
        self.search_service = search_service
        self.llm = llm
        self.lightrag = lightrag_wrapper

    async def search(
        self,
        query: str,
        top_k_documents: int = 3,
        top_k_results_per_doc: int = 2,
        strategy: str = "auto"  # 新增: "pageindex", "lightrag", "hybrid", "auto"
    ) -> GlobalSearchResult:
        """
        执行全局多文档搜索
        
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
        
        if strategy == "pageindex":
            return await self._search_pageindex(query, top_k_documents, top_k_results_per_doc)
        elif strategy == "lightrag":
            return await self._search_lightrag(query)
        else:  # hybrid
            return await self._search_hybrid(query, top_k_documents, top_k_results_per_doc)
        """
        执行全局多文档搜索

        Args:
            query: 用户问题
            top_k_documents: 选择最相关的文档数量
            top_k_results_per_doc: 每个文档返回的结果数量
        """
        start_time = time.time()
        print(f"[GlobalSearch] Starting global search for query: {query} (strategy: {strategy})")

        # 阶段1: 文档选择
        print(f"[GlobalSearch] Phase 1: Document Selection")
        candidates = await self._select_documents(query, top_k_documents)
        print(f"[GlobalSearch] Selected {len(candidates)} candidate documents")

        if not candidates:
            return GlobalSearchResult(
                query=query,
                final_answer="未找到相关文档。请先上传相关文档后再进行提问。",
                sources=[],
                document_selection_reasoning="没有可用的文档",
                total_documents_searched=0,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        # 阶段2: 并行检索每个文档
        print(f"[GlobalSearch] Phase 2: Parallel Retrieval")
        retrieval_results = await self._parallel_retrieval(
            query, candidates, top_k_results_per_doc
        )
        print(f"[GlobalSearch] Retrieved results from {len(retrieval_results)} documents")

        # 阶段3: 答案聚合
        print(f"[GlobalSearch] Phase 3: Answer Synthesis")
        final_answer, sources = await self._synthesize_answer(query, retrieval_results)
        print(f"[GlobalSearch] Final answer synthesized with {len(sources)} sources")

        processing_time = (time.time() - start_time) * 1000

        return GlobalSearchResult(
            query=query,
            final_answer=final_answer,
            sources=sources,
            document_selection_reasoning=candidates[0].reasoning if candidates else "",
            total_documents_searched=len(candidates),
            processing_time_ms=processing_time
        )

    async def _select_documents(
        self,
        query: str,
        top_k: int
    ) -> List[DocumentCandidate]:
        """
        阶段1: 基于 LLM 推理选择相关文档
        """
        # 获取所有已完成的文档（使用新的 SQLite 存储 API）
        all_documents = []
        completed_docs = await self.doc_store.list_completed_documents()

        for doc in completed_docs:
            # 获取文档树结构作为摘要
            tree = self.doc_service.get_tree(doc.id)
            if tree:
                # 提取文档的顶层标题和内容作为摘要
                summary = self._extract_document_summary(tree)
                all_documents.append({
                    "doc_id": doc.id,
                    "filename": doc.filename,
                    "format": doc.format,
                    "summary": summary
                })

        if not all_documents:
            return []

        print(f"[GlobalSearch] Found {len(all_documents)} completed documents")
        print(f"[GlobalSearch] Document summaries prepared, calling LLM for selection...")

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
            print(f"[GlobalSearch] Calling LLM API: {self.llm.client.base_url} with model {self.llm.model}")
            response = await asyncio.wait_for(
                self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=2000,
                    timeout=60.0
                ),
                timeout=120.0
            )
            print(f"[GlobalSearch] LLM response received")
        except asyncio.TimeoutError:
            print(f"[GlobalSearch] ERROR: LLM API call timed out after 120 seconds")
            raise Exception("LLM API 调用超时，请检查网络连接和 API 配置")
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
                candidates.append(DocumentCandidate(
                    doc_id=selected["doc_id"],
                    filename=doc_info["filename"],
                    format=doc_info["format"],
                    relevance_score=selected.get("relevance_score", 0.0),
                    reasoning=selected.get("reasoning", "")
                ))

        return candidates

    def _select_strategy(self, query: str) -> str:
        """
        自动选择最优策略
        
        启发式规则：
        - 短查询、事实性问题 → LightRAG (fast)
        - 长查询、需要深度分析 → PageIndex (deep)
        - 跨文档比较 → Hybrid
        """
        # 简单启发式：根据查询长度和关键词选择
        if not LIGHTRAG_AVAILABLE or not self.lightrag:
            return "pageindex"
        
        if len(query) < 20:
            return "lightrag"
        elif "比较" in query or "对比" in query or "difference" in query.lower():
            return "hybrid"
        else:
            return "hybrid"  # 默认使用 hybrid

    async def _search_pageindex(
        self,
        query: str,
        top_k_documents: int,
        top_k_results_per_doc: int
    ) -> GlobalSearchResult:
        """
        纯 PageIndex 搜索（原有逻辑）
        
        适用于：深度分析、单文档精读
        """
        start_time = time.time()
        print(f"[GlobalSearch] Using PageIndex strategy")

        # 阶段1: 文档选择
        print(f"[GlobalSearch] Phase 1: Document Selection")
        candidates = await self._select_documents(query, top_k_documents)
        print(f"[GlobalSearch] Selected {len(candidates)} candidate documents")

        if not candidates:
            return GlobalSearchResult(
                query=query,
                final_answer="未找到相关文档。请先上传相关文档后再进行提问。",
                sources=[],
                document_selection_reasoning="没有可用的文档",
                total_documents_searched=0,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        # 阶段2: 并行检索每个文档
        print(f"[GlobalSearch] Phase 2: Parallel Retrieval")
        retrieval_results = await self._parallel_retrieval(
            query, candidates, top_k_results_per_doc
        )
        print(f"[GlobalSearch] Retrieved results from {len(retrieval_results)} documents")

        # 阶段3: 答案聚合
        print(f"[GlobalSearch] Phase 3: Answer Synthesis")
        final_answer, sources = await self._synthesize_answer(query, retrieval_results)
        print(f"[GlobalSearch] Final answer synthesized with {len(sources)} sources")

        processing_time = (time.time() - start_time) * 1000

        return GlobalSearchResult(
            query=query,
            final_answer=final_answer,
            sources=sources,
            document_selection_reasoning=candidates[0].reasoning if candidates else "",
            total_documents_searched=len(candidates),
            processing_time_ms=processing_time
        )

    async def _search_lightrag(self, query: str) -> GlobalSearchResult:
        """
        纯 LightRAG 搜索
        
        适用于：快速事实检索、多文档概览
        """
        if not self.lightrag:
            raise ValueError("LightRAG not configured")
        
        start_time = time.time()
        print(f"[GlobalSearch] Using LightRAG strategy")
        
        # 直接调用 LightRAG（它已经处理了所有文档的索引）
        result = await self.lightrag.search(query, mode="hybrid")
        
        processing_time = (time.time() - start_time) * 1000
        
        return GlobalSearchResult(
            query=query,
            final_answer=result["answer"],
            sources=[],  # LightRAG 返回的答案已包含引用
            document_selection_reasoning="LightRAG hybrid search across all indexed documents",
            total_documents_searched=1,  # LightRAG 使用统一索引
            processing_time_ms=processing_time
        )

    async def _search_hybrid(
        self,
        query: str,
        top_k_documents: int,
        top_k_results_per_doc: int
    ) -> GlobalSearchResult:
        """
        混合搜索：LightRAG 快速筛选 + PageIndex 深度精读
        
        策略：
        1. 使用 LightRAG 快速获取相关文档和段落
        2. 对这些文档使用 PageIndex 进行深度树检索
        3. 综合生成答案
        
        当前简化版：直接使用 LightRAG 结果
        """
        # 当前简化：直接返回 LightRAG 结果
        # TODO: 实现更精细的 hybrid 逻辑
        return await self._search_lightrag(query)

    async def _parallel_retrieval(
        self,
        query: str,
        candidates: List[DocumentCandidate],
        top_k_per_doc: int
    ) -> List[Dict[str, Any]]:
        """
        阶段2: 并行检索每个候选文档
        """
        tasks = []
        for candidate in candidates:
            task = self._retrieve_from_document(
                query, candidate, top_k_per_doc
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤异常结果
        valid_results = []
        for result in results:
            if not isinstance(result, Exception) and result is not None:
                valid_results.append(result)

        return valid_results

    async def _retrieve_from_document(
        self,
        query: str,
        candidate: DocumentCandidate,
        top_k: int
    ) -> Optional[Dict[str, Any]]:
        """从单个文档中检索相关内容"""
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
                top_k=top_k
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
                        "reasoning_path": r.reasoning_path
                    }
                    for r in search_response.results
                ]
            }
        except Exception as e:
            print(f"Error retrieving from document {candidate.doc_id}: {e}")
            return None

    async def _synthesize_answer(
        self,
        query: str,
        retrieval_results: List[Dict[str, Any]]
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        阶段3: 聚合多个文档的答案片段，生成最终答案
        """
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
                sources.append({
                    "document_id": doc_result["doc_id"],
                    "document_name": doc_name,
                    "section_title": result["title"],
                    "page_refs": result["page_refs"],
                    "node_id": result["node_id"]
                })

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
            print(f"[GlobalSearch] Calling LLM for answer synthesis...")
            response = await asyncio.wait_for(
                self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=[{"role": "user", "content": synthesis_prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                    timeout=60.0
                ),
                timeout=120.0
            )
            print(f"[GlobalSearch] Answer synthesis completed")
        except asyncio.TimeoutError:
            print(f"[GlobalSearch] ERROR: Answer synthesis timed out")
            return "生成答案时超时，请稍后重试。", sources
        except Exception as e:
            print(f"[GlobalSearch] ERROR: Answer synthesis failed: {e}")
            return f"生成答案时出错：{str(e)}", sources

        final_answer = response.choices[0].message.content

        return final_answer, sources

    def _extract_document_summary(self, tree: Dict[str, Any]) -> str:
        """提取文档的摘要信息（顶层节点）"""
        nodes = tree.get("nodes", [])
        if not nodes:
            return "空文档"

        summaries = []
        for node in nodes[:3]:  # 只取前3个顶层节点
            title = node.get("title", "")
            content = node.get("content", "")[:200]  # 限制长度
            summaries.append(f"- {title}: {content}")

        return "\n".join(summaries)

    def _format_documents_for_llm(self, documents: List[Dict]) -> str:
        """格式化文档列表供 LLM 分析"""
        formatted = []
        for i, doc in enumerate(documents, 1):
            formatted.append(
                f"{i}. 文档ID: {doc['doc_id']}\n"
                f"   文件名: {doc['filename']}\n"
                f"   格式: {doc['format']}\n"
                f"   摘要:\n{doc['summary']}\n"
            )
        return "\n".join(formatted)
