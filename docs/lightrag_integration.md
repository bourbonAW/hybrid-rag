# LightRAG 集成文档

## 概述

本项目使用 [lightrag-hku](https://github.com/HKUDS/LightRAG) v1.4.10 官方库，实现了与 PageIndex 的混合检索能力。

## 架构说明

### 核心设计

```
lib/
├── lightrag/                    # LightRAG 模块目录
│   ├── __init__.py              # 导出 LightRAGWrapper
│   ├── wrapper.py               # 包装器实现
│   └── config.yaml              # 模块配置
```

### 职责划分

| 组件 | 职责 |
|------|------|
| `lib/lightrag/wrapper.py` | 适配 lightrag-hku API 到项目统一接口 |
| `services/global_search_service.py` | 策略选择，调用 LightRAG 或 PageIndex |
| `services/document_service.py` | 并行构建两种索引 |

## 配置

### 配置文件位置

- `lib/lightrag/config.yaml` - 模块默认配置
- `config/lightrag_config.yaml` - 项目级配置（可选，通过软链接或复制）

### 关键配置项

```yaml
# LLM 配置（复用项目配置）
llm:
  model: "gpt-4o-mini"
  max_async_calls: 4
  max_tokens: 4000

# 嵌入配置
embedding:
  model: "text-embedding-3-large"
  dimensions: 3072

# 分块配置
chunking:
  chunk_token_size: 1200
  chunk_overlap_token_size: 100

# 存储配置
storage:
  working_dir: "./storage/lightrag"
  kv_storage: "JsonKVStorage"
  vector_storage: "NanoVectorDBStorage"
  graph_storage: "NetworkXStorage"

# 检索配置
retrieval:
  default_mode: "hybrid"
  top_k: 60
```

## 使用方式

### 1. 直接调用 LightRAG

```python
from lib.lightrag import LightRAGWrapper

wrapper = LightRAGWrapper()
await wrapper.initialize()

# 索引文档
await wrapper.index_document("doc1", "文本内容")

# 查询
result = await wrapper.search("问题", mode="hybrid")
print(result["answer"])

# 关闭
await wrapper.close()
```

### 2. 通过 API 使用

```bash
# 使用 LightRAG 策略
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "问题",
    "strategy": "lightrag",
    "top_k_documents": 3,
    "top_k_results_per_doc": 2
  }'

# 使用混合策略
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "问题",
    "strategy": "hybrid"
  }'

# 使用 PageIndex 策略（原有逻辑）
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "问题",
    "strategy": "pageindex"
  }'
```

### 3. 策略选择

| 策略 | 适用场景 | 特点 |
|------|----------|------|
| `auto` | 默认 | 根据查询自动选择 |
| `pageindex` | 深度分析、单文档精读 | 精确，但较慢 |
| `lightrag` | 快速事实检索、多文档概览 | 快速，亚线性扩展 |
| `hybrid` | 跨文档比较、复杂问题 | 结合两者优势 |

## lightrag-hku 功能清单

以下功能由 lightrag-hku 官方库自动提供：

### 核心功能
- ✅ 文本分块（chunk_token_size, chunk_overlap_token_size）
- ✅ 实体提取（entity extraction）
- ✅ 关系抽取（relation extraction）
- ✅ 图构建（graph construction）
- ✅ 社区检测（community detection）
- ✅ 双层检索（local + global）
- ✅ 答案生成（answer generation）

### 查询模式
- `naive`: 基础向量检索
- `local`: 局部/实体级检索
- `global`: 全局/社区级检索
- `hybrid`: 混合检索（推荐）
- `mix`: 知识图 + 向量混合

### 存储后端
- ✅ JSON 文件存储（默认）
- ✅ Neo4j 图数据库
- ✅ PostgreSQL + AGE
- ✅ MongoDB
- ✅ Redis
- ✅ Milvus
- ✅ Faiss

### 其他功能
- ✅ 增量文档插入（ainsert）
- ✅ 文档删除（adelete_by_doc_id）
- ✅ 流式响应（stream=True）
- ✅ 重排序（rerank）
- ✅ 引用溯源（citation）
- ✅ Token 追踪（TokenTracker）

## API 参考

### LightRAGWrapper

#### 初始化

```python
wrapper = LightRAGWrapper(config_path: Optional[Path] = None)
await wrapper.initialize()
```

#### 索引文档

```python
result = await wrapper.index_document(
    document_id: str,      # 文档唯一标识
    text: str,             # 文档文本内容
    file_path: Optional[str] = None  # 文件路径（可选）
) -> Dict[str, Any]
```

返回：
```python
{
    "document_id": str,
    "status": "completed",
    "working_dir": str
}
```

#### 搜索

```python
result = await wrapper.search(
    query: str,            # 查询问题
    mode: str = "hybrid",  # 检索模式
    top_k: Optional[int] = None  # 检索数量限制
) -> Dict[str, Any]
```

返回：
```python
{
    "answer": str,        # 生成的答案
    "query": str,         # 原始查询
    "mode": str,          # 使用的检索模式
    "working_dir": str    # 工作目录
}
```

#### 批量搜索

```python
results = await wrapper.search_multi(
    queries: List[str],    # 查询列表
    mode: str = "hybrid"   # 检索模式
) -> List[Dict[str, Any]]
```

#### 删除文档

```python
success = await wrapper.delete_document(document_id: str) -> bool
```

#### 获取统计信息

```python
stats = await wrapper.get_stats() -> Dict[str, Any]
```

#### 关闭资源

```python
await wrapper.close()
```

## 测试

### 运行单元测试

```bash
# 运行 LightRAG wrapper 测试
uv run pytest tests/test_lightrag_wrapper.py -v

# 运行集成测试
uv run pytest tests/test_lightrag_integration.py -v -m integration

# 运行所有测试
uv run pytest tests/ -v
```

## 故障排除

### LightRAG 初始化失败

**症状**: 启动时 LightRAG 初始化失败

**解决**:
1. 检查 `lightrag-hku` 是否已安装: `uv pip list | grep lightrag`
2. 检查 OpenAI API key 配置: `echo $OPENAI_API_KEY`
3. 检查配置文件是否存在: `ls lib/lightrag/config.yaml`

### 索引构建缓慢

**症状**: 文档处理时间过长

**说明**: LightRAG 索引构建涉及实体提取、关系抽取、图构建等步骤，比 PageIndex 慢。

**解决**:
- 后台异步处理
- 调整分块参数减少块数量
- 使用更高性能的 LLM

### 存储目录权限问题

**症状**: `Permission denied` 错误

**解决**:
```bash
chmod -R 755 ./storage/lightrag
```

## 性能对比

| 指标 | PageIndex | LightRAG | 提升 |
|------|-----------|----------|------|
| 检索方式 | 树遍历 | 图遍历 + 双层检索 | - |
| Tokens/Query | 数千 | <100 | 1000x+ |
| 增量更新 | ❌ | ✅ | 关键 |
| 多文档扩展 | 线性恶化 | 亚线性 | 核心优势 |
| 延迟 | 5-15s | <1s | 10x+ |

## 参考

- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [LightRAG PyPI](https://pypi.org/project/lightrag-hku/)
- [LightRAG 论文](https://arxiv.org/abs/2410.05779)
