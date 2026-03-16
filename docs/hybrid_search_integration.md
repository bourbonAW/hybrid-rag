# Hybrid Search (BM25 + Vector) 集成文档

## 概述

Hybrid Search 是 hybrid-rag 项目的**第四个搜索策略**，结合了传统的 BM25 关键词检索和现代的向量语义检索，通过 RRF (Reciprocal Rank Fusion) 算法融合结果，在精确关键词匹配和语义相似性理解之间取得最佳平衡。

## 核心特性

- **BM25 (Lexical Retrieval)**: 精确匹配关键词、术语、ID、代码片段
- **Dense Vector (Semantic Retrieval)**: 理解语义相似性、概念关联
- **RRF Fusion**: 无需分数归一化的智能结果融合
- **内嵌存储**: 基于 Qdrant 内嵌模式，无需独立服务

## 技术架构

```
Query
  ↓
├─→ Sparse Retrieval (BM25/BM42) ─┐
├─→ Dense Retrieval (Embedding) ──┤
                                  ↓
                           RRF Fusion
                                  ↓
                          Ranked Results
```

### RRF (Reciprocal Rank Fusion) 原理

```
RRF_score(d) = Σ 1 / (k + rank_i(d))

其中:
- k = 60 (常数，防止高分文档垄断)
- rank_i(d) = 文档 d 在第 i 个检索结果中的排名
- 对 BM25 和 Vector 两个排名列表求和
```

**优点:**
- 无需分数归一化 (BM25 和 Cosine 分数不可比)
- 对异常值鲁棒
- 无需训练/调参

## 配置

### 配置文件

**路径**: `config/hybrid_search_config.yaml`

```yaml
# Hybrid Search 配置 (BM25 + Vector)

enabled: true

# 存储配置
storage:
  path: "./storage/hybrid_search"
  collection_name_template: "doc_{document_id}"

# Chunking 配置
chunking:
  chunk_size: 512
  chunk_overlap: 50
  separators: ["\n\n", "\n", ". ", " "]
  
# Embedding 配置
embedding:
  model: "BAAI/bge-small-en-v1.5"  # 384维，轻量快速
  dimensions: 384
  batch_size: 32

# Sparse/BM25 配置
sparse:
  enabled: true  # 使用 BM42 实现

# Hybrid 融合配置
fusion:
  method: "rrf"
  rrf_k: 60

# 检索配置
retrieval:
  top_k_sparse: 20   # BM25 检索数量
  top_k_dense: 20    # Vector 检索数量
  final_top_k: 10    # 融合后返回数量
```

### Embedding 模型选择

| 模型 | 维度 | 性能 | 适用场景 |
|------|------|------|----------|
| BAAI/bge-small-en-v1.5 | 384 | 快 | 英文文档 (推荐) |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | 快 | 通用场景 |
| BAAI/bge-m3 | 1024 | 慢 | 多语言支持 |

## API 使用

### 全局搜索端点

```bash
POST /api/v1/search
```

#### 请求示例

```json
{
  "query": "API endpoint authentication",
  "strategy": "hybrid_search",
  "top_k_documents": 3,
  "top_k_results_per_doc": 2
}
```

#### 策略选择

- `"auto"`: 自动选择（关键词查询会自动选择 hybrid_search）
- `"hybrid_search"`: 显式使用 BM25 + Vector Hybrid Search
- `"pageindex"`: 仅使用 PageIndex
- `"lightrag"`: 仅使用 LightRAG
- `"hirag"`: 仅使用 HiRAG
- `"hybrid"`: LightRAG + PageIndex 混合

### 自动策略选择规则

系统会根据查询特征自动选择最优策略：

```python
# 关键词导向查询 → Hybrid Search
if contains_keywords_like("function", "api", "id:", '"'):
    return "hybrid_search"

# 层次化查询 → HiRAG
if contains("层次", "结构", "关系"):
    return "hirag"

# 短查询 → LightRAG
if len(query) < 20:
    return "lightrag"

# 默认 → Hybrid Search
return "hybrid_search"
```

## 编程接口

### HybridSearchWrapper

```python
from lib.hybrid_search import HybridSearchWrapper

# 初始化
wrapper = HybridSearchWrapper()
await wrapper.initialize()

# 索引文档
result = await wrapper.index_document(
    document_id="doc_123",
    text="文档全文...",
    metadata={"filename": "example.txt"}
)

# 搜索
search_result = await wrapper.search(
    query="查询内容",
    document_id="doc_123",
    top_k=10
)

# 结果格式
{
    "query": "查询内容",
    "document_id": "doc_123",
    "results": [
        {
            "text": "匹配的文本片段...",
            "score": 0.085,  # RRF 融合分数
            "chunk_index": 0,
            "metadata": {...}
        }
    ],
    "total_results": 5
}

# 清理
await wrapper.close()
```

## 性能优化

### Chunking 调优

- **Chunk Size**: 512 tokens (默认)
  - 增大：更好的上下文，但降低精度
  - 减小：更高的精度，但可能丢失上下文
  
- **Overlap**: 50 tokens (默认)
  - 确保语义连续性
  - 建议为 chunk_size 的 10%

### Embedding 批处理

```yaml
embedding:
  batch_size: 32  # 根据内存调整
```

### RRF 参数

```yaml
fusion:
  rrf_k: 60  # 通常 50-100
```

- 较小的 k: 更重视排名靠前的结果
- 较大的 k: 更平衡地考虑所有结果

## 与其他策略对比

| 策略 | 优势 | 劣势 | 最佳场景 |
|------|------|------|----------|
| **hybrid_search** | 精确关键词 + 语义理解 | 需要更多存储 | 代码、术语、混合查询 |
| pageindex | TOC 树结构，适合长文档 | 无语义理解 | 结构化文档、书籍 |
| lightrag | 快速，实体关系 | 需要全局索引 | 多文档事实检索 |
| hirag | 层次化知识结构 | 索引较慢 | 复杂关系分析 |

## 存储结构

```
storage/
├── hybrid_search/
│   └── qdrant_db/           # Qdrant 内嵌数据库
│       ├── collections/     # 文档集合
│       └── meta.json        # 元数据
```

每个文档一个独立的 Collection，命名格式: `doc_{document_id}`

## 故障排除

### 模型下载慢

首次使用时会自动下载 embedding 模型：

```python
# 手动预下载模型
from qdrant_client.fastembed import TextEmbedding
TextEmbedding.download_model("BAAI/bge-small-en-v1.5")
```

### 内存不足

1. 使用更小的 embedding 模型
2. 减小 batch_size
3. 减小 chunk_size

### 检索结果不理想

1. 调整 chunk_size 和 overlap
2. 尝试不同的 embedding 模型
3. 调整 RRF k 值

## 测试

```bash
# 运行 Hybrid Search 单元测试
uv run pytest tests/test_hybrid_search_wrapper.py -v

# 运行集成测试
uv run pytest tests/test_hybrid_search_integration.py -v -m integration
```

## 参考

- [Qdrant Hybrid Search 文档](https://qdrant.tech/documentation/concepts/hybrid-search/)
- [Reciprocal Rank Fusion 论文](https://plg.uwaterloo.ca/~gvcormac/cormackijcnl09.pdf)
- [FastEmbed 文档](https://qdrant.github.io/fastembed/)
