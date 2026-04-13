"""Hybrid Search 包装层 — 固定大小分块 (S1) + 递归分块 (S2) + BM25/Vector 双通道检索.

对应 Weaviate 文章中最基础的两种分块策略的工程组合：
- S1 Fixed-Size Chunking: chunk_size=512, overlap=50，文章建议的 baseline 参数
- S2 Recursive Chunking: separators 按段落→行→句→词优先级递归切分

在分块基础上叠加 BM25 精确匹配 + Dense Vector 语义匹配 + RRF 融合，
填补其他 LLM 驱动策略在精确关键词匹配上的盲区。

适用场景：代码片段查找、精确术语检索、ID/编号匹配
策略详情：docs/chunking_strategy_mapping.md#34-hybrid-search

基于 Qdrant 实现 BM25 + Vector Hybrid Search。
"""

import uuid
import warnings
from pathlib import Path
from typing import Any

import yaml

# 用于生成稳定的 chunk point ID
_POINT_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class HybridSearchWrapper:
    """Hybrid Search 包装类.

    结合 BM25 (稀疏检索) 和 Dense Vector (语义检索)，
    使用 RRF (Reciprocal Rank Fusion) 融合结果。

    设计：所有文档共享同一个 Qdrant collection，通过 payload.doc_id 过滤。
    这是 Qdrant 官方推荐的多租户模式——避免 per-document collection 无法
    跨文档检索、BM25 IDF 统计被切分、资源浪费等问题。
    """

    def __init__(self, config_path: Path | None = None):
        """Initialize Hybrid Search wrapper."""
        # 延迟导入，避免在模块加载时出错
        from qdrant_client import AsyncQdrantClient, models
        from qdrant_client.qdrant_fastembed import SparseTextEmbedding, TextEmbedding

        self._AsyncQdrantClient = AsyncQdrantClient
        self._models_module = models
        self._TextEmbedding = TextEmbedding
        self._SparseTextEmbedding = SparseTextEmbedding

        # 加载配置
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.storage_path = Path(self.config["storage"]["path"])
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.collection_name: str = self.config["storage"]["collection_name"]

        self._client: Any | None = None
        self._dense_embedder: Any | None = None
        self._sparse_embedder: Any | None = None

    async def initialize(self) -> None:
        """初始化 Qdrant 客户端、embedding 模型和全局 collection."""
        if self._client is not None:
            return

        # models 已在 __init__ 中导入
        self._models = self._models_module

        # 初始化 Qdrant (内嵌模式)
        self._client = self._AsyncQdrantClient(
            path=str(self.storage_path / "qdrant_db")
        )

        # 初始化 embedding 模型 (懒加载，首次使用时下载)
        embed_model = self.config["embedding"]["model"]
        self._dense_embedder = self._TextEmbedding(model_name=embed_model)

        # 初始化 sparse embedding (BM42)
        if self.config["sparse"]["enabled"]:
            self._sparse_embedder = self._SparseTextEmbedding(
                model_name="Qdrant/bm42-all-minilm-l6-v2-attentions"
            )

        # 创建全局 collection 并为 doc_id 建索引，便于过滤
        await self._ensure_collection()

        print(
            f"[HybridSearchWrapper] Initialized: model={embed_model}, "
            f"collection={self.collection_name}"
        )

    async def index_document(
        self,
        document_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """为文档构建 Hybrid Search 索引.

        所有 chunk 写入同一个全局 collection，通过 payload.doc_id 区分。
        Point ID 使用 uuid5(doc_id, chunk_index) 保证幂等性——
        重复索引同一文档会覆盖旧的 chunk。

        Args:
            document_id: 文档唯一标识
            text: 文档全文
            metadata: 可选元数据 (filename, format, etc.)

        Returns:
            索引结果统计
        """
        if not self._client:
            raise RuntimeError("HybridSearch not initialized")
        assert self._dense_embedder is not None, "Dense embedder not initialized"

        print(f"[HybridSearchWrapper] Indexing document: {document_id}")

        # 1. 文本分块
        chunks = self._chunk_text(text)
        print(f"[HybridSearchWrapper] Created {len(chunks)} chunks")

        # 2. 先清理该文档旧 chunk（若存在），避免重复索引 chunk 数量变化时残留
        await self._delete_by_doc_id(document_id)

        # 3. 生成 embeddings
        dense_embeddings = list(self._dense_embedder.embed(chunks))
        sparse_embeddings = None
        if self._sparse_embedder:
            sparse_embeddings = list(self._sparse_embedder.embed(chunks))

        # 4. 准备 points（deterministic UUID 便于去重/覆盖）
        points = []
        for i, (chunk, dense_vec) in enumerate(zip(chunks, dense_embeddings, strict=False)):
            point_id = str(
                uuid.uuid5(_POINT_ID_NAMESPACE, f"{document_id}:{i}")
            )
            point = self._models.PointStruct(
                id=point_id,
                vector={
                    "dense": dense_vec.tolist(),
                },
                payload={
                    "text": chunk,
                    "chunk_index": i,
                    "doc_id": document_id,
                    **(metadata or {}),
                },
            )

            if sparse_embeddings:
                sparse_vec = sparse_embeddings[i]
                point.vector["sparse"] = self._models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                )

            points.append(point)

        # 5. 写入 Qdrant
        await self._client.upsert(collection_name=self.collection_name, points=points)

        return {
            "document_id": document_id,
            "chunks_count": len(chunks),
            "collection_name": self.collection_name,
            "status": "completed",
        }

    async def search(
        self,
        query: str,
        doc_ids: list[str] | None = None,
        top_k: int | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行全局 Hybrid Search 检索.

        默认在所有已索引文档中检索。传入 `doc_ids` 可将检索限定到指定文档子集。

        Args:
            query: 查询字符串
            doc_ids: 可选，限制检索范围的文档 ID 列表；None 表示全局检索
            top_k: 返回结果数量 (默认使用配置)
            filter_metadata: 可选的 payload 过滤条件（AND 语义）

        Returns:
            检索结果，包含 chunks 和融合分数（含 doc_id 以便溯源）
        """
        if not self._client:
            raise RuntimeError("HybridSearch not initialized")
        assert self._dense_embedder is not None, "Dense embedder not initialized"

        top_k = top_k or self.config["retrieval"]["final_top_k"]

        # 构建 payload 过滤器
        must_conditions = []
        if doc_ids:
            must_conditions.append(
                self._models.FieldCondition(
                    key="doc_id",
                    match=self._models.MatchAny(any=list(doc_ids)),
                )
            )
        if filter_metadata:
            for key, value in filter_metadata.items():
                must_conditions.append(
                    self._models.FieldCondition(
                        key=key,
                        match=self._models.MatchValue(value=value),
                    )
                )
        query_filter = (
            self._models.Filter(must=must_conditions) if must_conditions else None
        )

        # 生成 query embeddings
        dense_query = list(self._dense_embedder.embed([query]))[0]

        # Hybrid search with RRF；filter 同时作用于两路 prefetch
        dense_prefetch = self._models.Prefetch(
            query=dense_query.tolist(),
            using="dense",
            limit=self.config["retrieval"]["top_k_dense"],
            filter=query_filter,
        )
        sparse_prefetch = self._models.Prefetch(
            query=self._models.Document(
                text=query,
                model="Qdrant/bm42-all-minilm-l6-v2-attentions",
            )
            if self._sparse_embedder
            else dense_query.tolist(),
            using="sparse" if self._sparse_embedder else "dense",
            limit=self.config["retrieval"]["top_k_sparse"],
            filter=query_filter,
        )

        results = await self._client.query_points(
            collection_name=self.collection_name,
            prefetch=[dense_prefetch, sparse_prefetch],
            query=self._models.FusionQuery(fusion=self._models.Fusion.RRF),
            limit=top_k,
        )

        formatted_results = []
        for point in results.points:
            formatted_results.append({
                "text": point.payload.get("text", ""),
                "score": point.score,
                "chunk_index": point.payload.get("chunk_index"),
                "doc_id": point.payload.get("doc_id"),
                "metadata": {
                    k: v
                    for k, v in point.payload.items()
                    if k not in ["text", "chunk_index", "doc_id"]
                },
            })

        return {
            "query": query,
            "doc_ids": doc_ids,
            "results": formatted_results,
            "total_results": len(formatted_results),
        }

    def _chunk_text(self, text: str) -> list[str]:
        """递归文本分块.

        使用 RecursiveCharacterTextSplitter 策略。
        """
        chunk_size = self.config["chunking"]["chunk_size"]
        chunk_overlap = self.config["chunking"]["chunk_overlap"]
        separators = self.config["chunking"]["separators"]

        chunks: list[str] = []
        if len(text) <= chunk_size:
            return [text]

        # 按分隔符递归分割
        for sep in separators:
            if sep in text and len(text) > chunk_size:
                parts = text.split(sep)
                current_chunk = ""
                for part in parts:
                    test_chunk = (sep if current_chunk else "") + part
                    if len(current_chunk) + len(test_chunk) <= chunk_size:
                        current_chunk += test_chunk
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = part
                if current_chunk:
                    chunks.append(current_chunk)
                break

        # 如果没有合适的分隔符，直接按字符切割
        if not chunks:
            step = chunk_size - chunk_overlap
            chunks = [text[i : i + chunk_size] for i in range(0, len(text), step)]

        return chunks

    async def _ensure_collection(self) -> None:
        """创建全局 collection 并为 doc_id 建立 payload 索引（幂等）."""
        assert self._client is not None, "Client not initialized"

        exists = await self._client.collection_exists(self.collection_name)
        if not exists:
            dims = self.config["embedding"]["dimensions"]
            await self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": self._models.VectorParams(
                        size=dims,
                        distance=self._models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": self._models.SparseVectorParams()
                }
                if self.config["sparse"]["enabled"]
                else None,
            )

        # 为 doc_id 建 payload 索引以加速过滤。
        # 注意：Qdrant 嵌入（本地）模式下 payload 索引是 no-op，官方会发 UserWarning。
        # 当前目录式本地存储规模小，线性过滤够用；保留此调用是为了切换到服务端模式时
        # 自动生效。这里抑制那条噪音 warning。
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*Payload indexes have no effect in the local Qdrant.*",
                    category=UserWarning,
                )
                await self._client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="doc_id",
                    field_schema=self._models.PayloadSchemaType.KEYWORD,
                )
        except Exception:
            pass

    async def _delete_by_doc_id(self, document_id: str) -> int:
        """按 doc_id 过滤删除该文档的所有 chunk. 返回删除前的匹配数（best-effort）."""
        assert self._client is not None, "Client not initialized"
        await self._client.delete(
            collection_name=self.collection_name,
            points_selector=self._models.FilterSelector(
                filter=self._models.Filter(
                    must=[
                        self._models.FieldCondition(
                            key="doc_id",
                            match=self._models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )
        return 0

    async def delete_document(self, document_id: str) -> bool:
        """删除指定文档的所有 chunk（按 payload.doc_id 过滤）."""
        if not self._client:
            return False
        try:
            await self._delete_by_doc_id(document_id)
            return True
        except Exception as e:
            print(f"[HybridSearchWrapper] delete failed for {document_id}: {e}")
            return False

    async def close(self) -> None:
        """关闭资源."""
        if self._client:
            await self._client.close()
            self._client = None
