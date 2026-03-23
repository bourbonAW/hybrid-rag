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

from pathlib import Path
from typing import Any

import yaml


class HybridSearchWrapper:
    """Hybrid Search 包装类.

    结合 BM25 (稀疏检索) 和 Dense Vector (语义检索)，
    使用 RRF (Reciprocal Rank Fusion) 融合结果。
    """

    def __init__(self, config_path: Path | None = None):
        """Initialize Hybrid Search wrapper."""
        # 延迟导入，避免在模块加载时出错
        from qdrant_client import AsyncQdrantClient, models
        from qdrant_client.fastembed import SparseTextEmbedding, TextEmbedding

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

        self._client: Any | None = None
        self._dense_embedder: Any | None = None
        self._sparse_embedder: Any | None = None

    async def initialize(self) -> None:
        """初始化 Qdrant 客户端和 embedding 模型."""
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

        print(f"[HybridSearchWrapper] Initialized with model: {embed_model}")

    async def index_document(
        self,
        document_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """为文档构建 Hybrid Search 索引.

        Args:
            document_id: 文档唯一标识
            text: 文档全文
            metadata: 可选元数据 (filename, format, etc.)

        Returns:
            索引结果统计
        """
        if not self._client:
            raise RuntimeError("HybridSearch not initialized")
        # 确保 embedder 已初始化
        assert self._dense_embedder is not None, "Dense embedder not initialized"

        print(f"[HybridSearchWrapper] Indexing document: {document_id}")

        # 1. 文本分块
        chunks = self._chunk_text(text)
        print(f"[HybridSearchWrapper] Created {len(chunks)} chunks")

        # 2. 创建 collection (如果不存在)
        collection_name = self._get_collection_name(document_id)
        await self._create_collection_if_not_exists(collection_name)

        # 3. 生成 embeddings
        dense_embeddings = list(self._dense_embedder.embed(chunks))
        sparse_embeddings = None
        if self._sparse_embedder:
            sparse_embeddings = list(self._sparse_embedder.embed(chunks))

        # 4. 准备 points
        points = []
        for i, (chunk, dense_vec) in enumerate(zip(chunks, dense_embeddings, strict=False)):
            point = self._models.PointStruct(
                id=i,
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

            # 添加 sparse vector
            if sparse_embeddings:
                sparse_vec = sparse_embeddings[i]
                point.vector["sparse"] = self._models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                )

            points.append(point)

        # 5. 写入 Qdrant
        await self._client.upsert(collection_name=collection_name, points=points)

        return {
            "document_id": document_id,
            "chunks_count": len(chunks),
            "collection_name": collection_name,
            "status": "completed",
        }

    async def search(
        self,
        query: str,
        document_id: str,
        top_k: int | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行 Hybrid Search 检索.

        Args:
            query: 查询字符串
            document_id: 目标文档 ID
            top_k: 返回结果数量 (默认使用配置)
            filter_metadata: 可选的元数据过滤

        Returns:
            检索结果，包含 chunks 和融合分数
        """
        if not self._client:
            raise RuntimeError("HybridSearch not initialized")
        # 确保 embedder 已初始化
        assert self._dense_embedder is not None, "Dense embedder not initialized"

        collection_name = self._get_collection_name(document_id)

        # 检查 collection 是否存在
        exists = await self._client.collection_exists(collection_name)
        if not exists:
            return {
                "query": query,
                "results": [],
                "error": f"Document {document_id} not indexed",
            }

        top_k = top_k or self.config["retrieval"]["final_top_k"]

        # 生成 query embeddings
        dense_query = list(self._dense_embedder.embed([query]))[0]

        # 执行 hybrid search with RRF
        results = await self._client.query_points(
            collection_name=collection_name,
            prefetch=[
                # Dense retrieval
                self._models.Prefetch(
                    query=dense_query.tolist(),
                    using="dense",
                    limit=self.config["retrieval"]["top_k_dense"],
                ),
                # Sparse retrieval (BM25/BM42)
                self._models.Prefetch(
                    query=self._models.Document(
                        text=query,
                        model="Qdrant/bm42-all-minilm-l6-v2-attentions",
                    )
                    if self._sparse_embedder
                    else dense_query.tolist(),
                    using="sparse" if self._sparse_embedder else "dense",
                    limit=self.config["retrieval"]["top_k_sparse"],
                ),
            ],
            query=self._models.FusionQuery(fusion=self._models.Fusion.RRF),
            limit=top_k,
        )

        # 格式化结果
        formatted_results = []
        for point in results.points:
            formatted_results.append({
                "text": point.payload.get("text", ""),
                "score": point.score,
                "chunk_index": point.payload.get("chunk_index"),
                "metadata": {
                    k: v
                    for k, v in point.payload.items()
                    if k not in ["text", "chunk_index", "doc_id"]
                },
            })

        return {
            "query": query,
            "document_id": document_id,
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

    async def _create_collection_if_not_exists(self, collection_name: str) -> None:
        """创建 Qdrant collection (如果不存在)."""
        assert self._client is not None, "Client not initialized"
        exists = await self._client.collection_exists(collection_name)
        if exists:
            return

        dims = self.config["embedding"]["dimensions"]

        await self._client.create_collection(
            collection_name=collection_name,
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

    def _get_collection_name(self, document_id: str) -> str:
        """生成 collection 名称."""
        template = self.config["storage"]["collection_name_template"]
        return template.format(document_id=document_id.replace("-", "_"))

    async def delete_document(self, document_id: str) -> bool:
        """删除文档索引."""
        if not self._client:
            return False

        collection_name = self._get_collection_name(document_id)
        exists = await self._client.collection_exists(collection_name)
        if exists:
            await self._client.delete_collection(collection_name)
            return True
        return False

    async def close(self) -> None:
        """关闭资源."""
        if self._client:
            await self._client.close()
            self._client = None
