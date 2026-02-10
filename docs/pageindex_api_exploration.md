# PageIndex API 探索报告

## 关键发现

### 1. 实际的函数签名

**PDF 处理：**
```python
def page_index(
    doc,                          # PDF 文件路径
    model=None,                   # LLM 模型
    toc_check_page_num=None,      # 检查 TOC 的页数
    max_page_num_each_node=None,  # 每节点最大页数
    max_token_num_each_node=None, # 每节点最大 token 数
    if_add_node_id=None,          # 是否添加节点 ID
    if_add_node_summary=None,     # 是否添加节点摘要
    if_add_doc_description=None,  # 是否添加文档描述
    if_add_node_text=None         # 是否添加节点文本
)
```

**Markdown 处理：**
```python
async def md_to_tree(
    md_path,                      # Markdown 文件路径
    if_thinning=False,            # 是否精简树结构
    min_token_threshold=None,     # 精简阈值
    if_add_node_summary='no',     # 是否添加节点摘要
    summary_token_threshold=None, # 摘要 token 阈值
    model=None,                   # LLM 模型
    if_add_doc_description='no',  # 是否添加文档描述
    if_add_node_text='no',        # 是否添加节点文本
    if_add_node_id='yes'          # 是否添加节点 ID
)
```

### 2. 返回格式

**两者都返回相同的字典结构：**
```python
{
    'doc_name': str,              # 文档名称（不含扩展名）
    'doc_description': str,       # 文档描述（如果启用）
    'structure': [                # 树结构
        {
            'title': str,
            'node_id': str,       # 例如 "0001", "0001.0001"
            'summary': str,       # 节点摘要（如果启用）
            'text': str,          # 节点文本（如果启用）
            'physical_index': int,# PDF 的物理页码
            'line_num': int,      # Markdown 的行号
            'nodes': [...]        # 子节点
        }
    ]
}
```

### 3. 与计划的差异

**❌ 计划中的假设（错误）：**
```python
from pageindex.page_index import page_index
from pageindex.page_index_md import page_index_md  # ❌ 不存在
```

**✅ 实际的导入方式：**
```python
from pageindex.page_index import page_index
from pageindex.page_index_md import md_to_tree  # ✅ 正确
```

### 4. 配置管理

PageIndex 使用 `ConfigLoader` 类加载配置：
- 接受 YAML 配置文件或参数字典
- 参数优先级：函数参数 > YAML 配置
- 配置通过 `SimpleNamespace` 对象传递

### 5. 关键特性确认

**✅ TOC 三模式处理**（确认存在）：
- `process_toc_with_page_numbers`: 有 TOC 和页码
- `process_toc_no_page_numbers`: 有 TOC 但无页码
- `process_no_toc`: 没有 TOC

**✅ 验证循环**（确认存在）：
- `verify_toc()`: 验证提取的结构准确性
- `fix_incorrect_toc_with_retries()`: 修复错误
- `validate_and_truncate_physical_indices()`: 验证物理索引

**✅ 递归分割**（确认存在）：
- `process_large_node_recursively()`: 自动分割大节点
- 基于 `max_page_num_each_node` 和 `max_token_num_each_node`

### 6. 使用建议

**PDF 处理：**
```python
result = page_index(
    doc="/path/to/file.pdf",
    model="gpt-4o-2024-11-20",
    if_add_node_summary="yes",
    if_add_doc_description="yes",
    if_add_node_text="no"
)
```

**Markdown 处理：**
```python
result = await md_to_tree(
    md_path="/path/to/file.md",
    if_add_node_summary="yes",
    if_add_doc_description="yes",
    model="gpt-4o-2024-11-20"
)
```

### 7. Phase 2 需要调整的地方

1. **包装层函数名**：
   - `build_tree_from_markdown()` 应该调用 `md_to_tree()`，不是 `page_index_md()`

2. **参数传递方式**：
   - `page_index()` 不接受 `opt` 对象，而是直接接受参数
   - 需要从 YAML 配置中提取参数并传递

3. **异步处理**：
   - `md_to_tree()` 是异步函数，需要 `await`
   - `page_index()` 是同步函数，内部使用 `asyncio.run()`

4. **返回格式统一**：
   - 两者返回格式已经统一（都是 `{doc_name, doc_description, structure}`）
   - 无需复杂的 `_normalize_tree()` 转换
   - 只需要将 `structure` 包装到 `nodes` 键中以匹配我们的 API 格式
