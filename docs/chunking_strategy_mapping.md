# RAG 分块策略映射：从理论到工程落地

> **参考文章**: [Chunking Strategies for RAG](https://weaviate.io/blog/chunking-strategies-for-rag) (Weaviate)
> **项目**: PageIndex API Service — 多策略 RAG 检索系统
> **更新日期**: 2026-03-23

---

## 1. 概述

本文档建立了 Weaviate 文章中 9 种 RAG 分块策略与本项目 4 个检索组件之间的系统映射关系。

文章的核心观点是：**分块质量直接决定 RAG 系统的检索效果，比向量数据库和嵌入模型的选择更重要**。本项目通过组合 4 个互补的检索组件，覆盖了文章 9 种策略中的 7 种，并通过智能体协调层（`GlobalSearchService`）在检索时动态选择最优策略。

### 项目 RAG 架构总览

```
文档上传 → 并行构建 4 种索引 → 查询时智能策略选择 → 检索 + 答案合成

索引层:
├── PageIndex    (树结构索引)     → 深度分析、单文档精读
├── LightRAG     (知识图谱索引)   → 快速事实检索、多文档概览
├── HiRAG        (层次聚类索引)   → 复杂关系分析
└── Hybrid Search (BM25+向量索引) → 精确关键词匹配

协调层:
└── GlobalSearchService._select_strategy()  → 根据查询特征路由到最优策略
```

---

## 2. 策略全景图

### 2.1 映射表

| 编号 | 文章策略 | 复杂度 | 项目对应组件 | 映射关系说明 |
|------|---------|--------|-------------|-------------|
| S1 | Fixed-Size Chunking (固定大小分块) | 基础 | Hybrid Search | `chunk_size=512, overlap=50`，作为 BM25+Vector 的基础分块单元 |
| S2 | Recursive Chunking (递归分块) | 基础 | Hybrid Search | `separators=["\n\n", "\n", ". ", " "]`，按自然边界优先级递归切分 |
| S3 | Document-Based Chunking (文档结构分块) | 基础 | PageIndex | 按 PDF 页面布局 / Markdown 标题层级切分，`md_to_tree()` / `page_index()` |
| S4 | Semantic Chunking (语义分块) | 进阶 | LightRAG | 通过实体抽取+关系图构建实现语义边界识别，比标准 embedding 相似度更深入 |
| S5 | LLM-Based Chunking (LLM 分块) | 进阶 | PageIndex | VLM/LLM 直接分析文档结构生成层次化树节点，最语义感知的分块方式 |
| S6 | Agentic Chunking (智能体分块) | 进阶 | GlobalSearchService | `_select_strategy()` 根据查询特征动态选择最优检索策略 |
| S7 | Late Chunking (延迟分块) | 进阶 | **未采用** | 需要长上下文嵌入模型支持，见"未来演进" |
| S8 | Hierarchical Chunking (层次化分块) | 进阶 | PageIndex + HiRAG | PageIndex 的树结构 = 显式层次；HiRAG 的 GMM 聚类 = 隐式层次（三层检索是 S8 多粒度检索的体现） |
| S9 | Adaptive Chunking (自适应分块) | 进阶 | **未采用** | 需要语义密度评估，见"未来演进" |

### 2.2 设计哲学

本项目没有选择单一的"最优"分块策略，而是采用了**多策略组合 + 智能路由**的架构。这个设计基于文章的一个关键洞察：

> "When a RAG system performs poorly, the issue is often not the retriever — it's the chunks."

不同类型的查询需要不同粒度的分块：精确关键词匹配需要小而密的 chunk（S1+S2），深度文档分析需要保留层次结构的树节点（S3+S5+S8），跨文档事实检索需要语义驱动的实体-关系网络（S4）。

`GlobalSearchService._select_strategy()` 作为 S6 Agentic Chunking 在检索层的工程落地，将"选择哪种分块策略"的决策从索引时推迟到查询时，让系统能够根据每次查询的特征选择最优路径。

---

## 3. 组件详解

### 3.1 PageIndex — 文档结构分块 (S3) + LLM 分块 (S5) + 层次化分块 (S8)

**理论依据**

PageIndex 同时体现了文章中 3 种策略的融合：

- **S3 Document-Based Chunking**: 按 PDF 页面布局和 Markdown 标题层级切分，尊重作者的文档组织意图。这是最自然的分块方式——文档的章节结构本身就是最好的语义边界。
- **S5 LLM-Based Chunking**: 不是用正则表达式解析标题，而是让 VLM/LLM 直接"理解"文档并生成树节点。对于扫描件、复杂排版的 PDF，这比规则解析可靠得多。
- **S8 Hierarchical Chunking**: 输出是多层级树结构（`node_id: "0001.0001.0002"`），支持从粗到细的渐进式检索。顶层节点给出全局概览，底层节点提供细节。

**设计决策**

为什么选 PageIndex 而不是 LlamaIndex 的 `HierarchicalNodeParser`？

- PageIndex 专注于"目录检测+树构建"，FinanceBench 98.7% 准确率
- VLM 模式可以处理扫描件/非结构化 PDF，不依赖文本提取质量
- 输出的树结构直接可用于 LLM 推理检索，无需额外向量化

**适用场景**

长文档深度分析、单文档精读、结构化报告（财务/法律/技术手册）

**代码入口**

| 方法 | 文件 | 策略映射 |
|------|------|---------|
| `PageIndexWrapper.build_tree_from_pdf()` | `services/pageindex_wrapper.py` | S3 + S5 |
| `PageIndexWrapper.build_tree_from_markdown()` | `services/pageindex_wrapper.py` | S3 + S8（结构来自标题语法，非 LLM 识别，故不计 S5；LLM 仅用于可选的摘要生成） |
| `SearchService.search()` | `services/search_service.py` | 基于树的推理检索 |

---

### 3.2 LightRAG — 语义分块的图增强变体 (S4)

**理论依据**

文章的 S4 Semantic Chunking 基于 embedding 相似度在连续句子之间找语义断点。LightRAG 走得更远——它用 LLM 抽取实体和关系，构建知识图谱，本质上是以"实体-关系"为语义单元的分块方式。

与标准 Semantic Chunking 的关键区别：

| 维度 | 标准 Semantic Chunking | LightRAG |
|------|----------------------|----------|
| 语义单元 | 连续句子组 | 实体节点 + 社区摘要 |
| 边界识别 | embedding cosine 相似度 | LLM 实体抽取 + 关系图 |
| 输出 | 文本片段 | 知识图谱 (实体+关系+社区) |
| 检索方式 | 向量相似度 | 图遍历 + 双层检索 (local/global) |

**设计决策**

为什么用 LightRAG 而不是自己实现标准 Semantic Chunking？

- 标准 Semantic Chunking 只解决"在哪切"，LightRAG 同时解决了"切完怎么检索"
- `<100 tokens/query` vs PageIndex 数千 tokens，多文档场景下成本优势显著
- 增量更新能力（`ainsert`），不需要全量重建索引

**适用场景**

快速事实检索、多文档概览、实体关系查询

**代码入口**

| 方法 | 文件 | 策略映射 |
|------|------|---------|
| `LightRAGWrapper.index_document()` | `lib/lightrag/wrapper.py` | S4 (实体抽取+图构建) |
| `GlobalSearchService._search_lightrag()` | `services/global_search_service.py` | 图检索 |

---

### 3.3 HiRAG — 层次化分块 (S8)

**理论依据**

HiRAG 是 S8 Hierarchical Chunking 的深度实现。与 PageIndex 基于文档显式结构（标题/目录）构建层次不同，HiRAG 通过 GMM 聚类自动发现内容中的隐含层次结构。

它的三层检索（chunk → community → global）是 S8 多粒度检索能力的体现——在不同层级获取不同粒度的信息，这是层次化分块的核心价值。

**与 PageIndex 层次化的区别**

| 维度 | PageIndex (S8-显式) | HiRAG (S8-隐式) |
|------|-------------------|-----------------|
| 层次来源 | 文档标题/目录结构 | GMM 聚类自动发现 |
| 适用文档 | 有明确章节结构的文档 | 任意文档，包括无标题结构的 |
| 层次粒度 | 由文档结构决定 | 由聚类算法决定 |
| 检索方式 | LLM 树遍历推理 | 三层分级检索 |

**适用场景**

复杂关系分析、层次化知识检索、无明确标题结构的文档

**代码入口**

| 方法 | 文件 | 策略映射 |
|------|------|---------|
| `HiRAGWrapper.index_document()` | `lib/hirag_wrapper/wrapper.py` | S8 (GMM 聚类 + 三层检索) |
| `GlobalSearchService._search_hirag()` | `services/global_search_service.py` | 层次化检索 |

---

### 3.4 Hybrid Search — 固定大小分块 (S1) + 递归分块 (S2)

**理论依据**

这是文章中最基础的两种策略的工程组合：

- **S1 Fixed-Size Chunking**: `chunk_size=512, overlap=50` 对文本做固定窗口切分。文章建议的起步参数是 512 tokens + 10% overlap，本项目完全遵循这个 baseline。
- **S2 Recursive Chunking**: `separators=["\n\n", "\n", ". ", " "]` 按优先级递归切分。先尝试段落分隔，段落太大则按行分，行太长则按句分，最后才按空格分。避免在语义单元中间硬切。

在分块基础上叠加了双通道检索：
- **BM25 (Sparse Retrieval)**: 精确匹配关键词、术语、ID
- **Dense Vector (Semantic Retrieval)**: 理解语义相似性
- **RRF Fusion**: 无需分数归一化的智能结果融合

**设计决策**

为什么保留这种"简单"策略？

文章的核心建议是：**先用 Fixed-Size 建立 baseline，再逐步优化**。Hybrid Search 就是这个 baseline，但叠加了 BM25 精确匹配能力，填补了其他策略的盲区——PageIndex/LightRAG/HiRAG 都依赖 LLM 理解，无法精确匹配术语和代码片段。

**适用场景**

代码片段查找、精确术语检索、ID/编号匹配、关键词导向查询

**代码入口**

| 方法 | 文件 | 策略映射 |
|------|------|---------|
| `HybridSearchWrapper.index_document()` | `lib/hybrid_search/wrapper.py` | S1 + S2 (分块 + 双通道索引) |
| 分块参数配置 | `lib/hybrid_search/config.yaml` | S1 参数: chunk_size, overlap |
| `GlobalSearchService._search_hybrid_search()` | `services/global_search_service.py` | RRF 融合检索 |

---

### 3.5 GlobalSearchService — 智能体协调层 (S6)

**理论依据**

文章的 S6 Agentic Chunking 描述了"AI agent 根据文档特征动态选择最优分块策略"的理念。`GlobalSearchService._select_strategy()` 是这个理念在**检索层**的工程落地——它根据查询特征（而非文档特征）选择最优的检索策略。

这是对文章理念在更高抽象层级的实现：文章讨论的是"对同一文档选择不同分块方式"，本项目将其提升为"对同一查询选择不同检索路径"——因为在多策略并行索引的架构下，分块已经在索引时完成了，真正需要动态决策的是检索时的策略选择。

**启发式路由规则**

| 查询特征 | 路由策略 | 理由 |
|---------|---------|------|
| 包含代码/术语/ID 关键词 | Hybrid Search | BM25 精确匹配 |
| 短查询 (<20 字符) | LightRAG | 图检索快速响应 |
| 包含"层次/结构/关系" | HiRAG | 层次化检索 |
| 包含"比较/对比" | Hybrid (LightRAG+PageIndex) | 跨文档综合（当前简化为 LightRAG） |
| 长查询/其他 | Hybrid Search (默认) 或 PageIndex (无 Hybrid Search 时) | 默认路径，BM25+Vector 覆盖面最广 |

**代码入口**

| 方法 | 文件 | 策略映射 |
|------|------|---------|
| `GlobalSearchService._select_strategy()` | `services/global_search_service.py` | S6 (策略路由) |
| `GlobalSearchService.search()` | `services/global_search_service.py` | 统一查询入口 |

---

## 4. 未来演进

以下是文章中提到但本项目尚未采用的策略，以及可能的落地路径。

### 4.1 Late Chunking (S7) — 优先级：中

**文章描述**

先将整个文档输入长上下文嵌入模型生成 token 级别的 embedding，然后再切分 chunk。每个 chunk 的 embedding 保留了全文档的上下文信息，解决了标准分块方式中"chunk 不知道其他 chunk 内容"的问题。

**当前差距**

Hybrid Search 的 embedding 是 chunk 级别的（`bge-small-en-v1.5`，384 维），每个 chunk 独立嵌入。文档中的跨段落引用（"如前所述"、"参见第三章"）会丢失上下文。

**落地路径**

1. 替换 Hybrid Search 的 embedding 流程：用长上下文模型（如 `jina-embeddings-v3`，支持 8192 tokens）对全文生成 token embedding
2. 按现有 S1+S2 规则切分，chunk embedding 通过平均对应 token embedding 得到
3. 改动集中在 `lib/hybrid_search/wrapper.py` 的 embedding 阶段，检索逻辑不变

**适用场景**: 技术手册、案例分析报告等包含大量交叉引用的文档

---

### 4.2 Adaptive Chunking (S9) — 优先级：低

**文章描述**

根据文本的语义密度动态调整 chunk_size 和 overlap。密集段落用小 chunk 提高精度，稀疏段落用大 chunk 保留上下文。

**当前差距**

Hybrid Search 使用固定参数 `chunk_size=512, overlap=50`，不区分文档内部的密度差异。一份年报中密集的财务数据表和稀疏的管理层讨论使用相同的分块粒度。

**落地路径**

1. 在 Hybrid Search 的分块阶段引入密度评估：计算每个段落的信息熵或实体密度
2. 高密度段落：`chunk_size=256, overlap=64`
3. 低密度段落：`chunk_size=1024, overlap=100`
4. 可以复用 LightRAG 的实体抽取结果来评估密度，避免额外 LLM 调用

**适用场景**: 结构混合型文档（年报、综合技术方案等）

---

### 4.3 Post-Chunking (查询时分块) — 优先级：低

**文章描述**

不在索引时分块，而是先嵌入整个文档，在查询时再根据查询意图动态决定分块方式。

**当前差距**

所有策略都是 Pre-Chunking：文档上传时完成分块和索引。优点是查询快，缺点是分块方式固定。

**落地路径**

1. 在 `SearchService` 中增加一种模式：对已有全文存储（`content.txt`）的文档，允许查询时根据 query 动态切分
2. 用 LLM 分析 query 特征决定最优 chunk_size
3. 适合作为 PageIndex 的补充：树检索定位到相关章节后，对章节内容做 query-aware 的二次分块

**适用场景**: 高价值查询、需要精确段落定位的场景（法律条款引用）

---

### 优先级总结

| 策略 | 优先级 | 理由 | 预估工作量 |
|------|--------|------|-----------|
| Late Chunking (S7) | 中 | 改善跨引用检索质量，改动集中在 embedding 层 | 1-2 周 |
| Adaptive Chunking (S9) | 低 | 优化边际收益，需要密度评估模型 | 2-3 周 |
| Post-Chunking | 低 | 增加查询延迟，仅适用于特定高价值场景 | 3-4 周 |

---

## 5. 参考

- [Chunking Strategies for RAG](https://weaviate.io/blog/chunking-strategies-for-rag) — Weaviate Blog, 本文档的理论框架来源
- [PageIndex](https://github.com/VectifyAI/PageIndex) — MIT 协议, 无向量的层次化 RAG 框架
- [LightRAG](https://github.com/HKUDS/LightRAG) — 知识图谱增强的轻量 RAG
- [HiRAG](https://arxiv.org/abs/2503.10150) — 层次化图增强 RAG
- [Qdrant Hybrid Search](https://qdrant.tech/documentation/concepts/hybrid-search/) — BM25+Vector 混合检索
- [RRF 论文](https://plg.uwaterloo.ca/~gvcormac/cormackijcnl09.pdf) — Reciprocal Rank Fusion
