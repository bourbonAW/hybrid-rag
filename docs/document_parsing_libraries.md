# Python 文档解析库调研

## PageIndex 官方支持

根据 lib/pageindex/requirements.txt 和代码分析：

### 官方支持的格式
1. **PDF**: 
   - 使用 `pymupdf` (1.26.4) 和 `PyPDF2` (3.0.1)
   - 通过 `page_index()` 函数处理
   - 支持 TOC 检测、页面提取、图像处理

2. **Markdown**:
   - 通过 `md_to_tree()` 函数处理
   - 直接解析 Markdown 标题结构 (# ## ###)
   - 代码: `lib/pageindex/pageindex/page_index_md.py`
   - 核心逻辑：
     * `extract_nodes_from_markdown()` - 提取所有标题
     * `extract_node_text_content()` - 提取每个节点的文本内容
     * 按标题层级构建树结构

### PageIndex 没有原生支持的格式
- **DOCX**: ❌ 不在官方依赖中
- **TXT**: 可以作为 Markdown 处理（无标题结构）
- **HTML**: ❌ 不支持
- **RTF**: ❌ 不支持

## 社区推荐的文档解析库

### 1. python-docx (官方推荐)
- **PyPI**: https://pypi.org/project/python-docx/
- **用途**: Word (.docx) 文件读写
- **优点**:
  * 官方维护，稳定可靠
  * 支持样式提取 (Heading 1-6, Normal)
  * 支持表格、图片、段落
  * API 简单直观
- **缺点**:
  * 只支持 .docx (不支持 .doc)
  * 不支持复杂格式（如嵌入对象）
- **我们当前使用**: ✅

### 2. mammoth (HTML 转换专家)
- **PyPI**: https://pypi.org/project/mammoth/
- **用途**: DOCX → HTML/Markdown
- **优点**:
  * 更好的样式保留
  * 生成干净的 HTML/Markdown
  * 处理复杂格式
- **缺点**:
  * 主要用于转换，不是解析
  * 依赖 HTML 中间格式

### 3. docx2txt
- **PyPI**: https://pypi.org/project/docx2txt/
- **用途**: DOCX → 纯文本
- **优点**: 非常简单，提取纯文本
- **缺点**: 丢失所有格式信息

### 4. Unstructured (企业级选择)
- **PyPI**: https://pypi.org/project/unstructured/
- **GitHub**: https://github.com/Unstructured-IO/unstructured
- **用途**: 多格式文档解析 (PDF, DOCX, HTML, 等)
- **优点**:
  * 支持 20+ 种文档格式
  * 智能元素检测 (标题、表格、列表)
  * 企业级功能
  * 与 LangChain/LlamaIndex 集成
- **缺点**:
  * 依赖多（安装包大）
  * 对简单场景过于复杂
  * 部分功能需要外部服务 (OCR, 布局分析)

### 5. pandoc (通用转换器)
- **工具**: 需要安装 pandoc 二进制文件
- **Python 包**: pypandoc
- **用途**: 任意格式互转
- **优点**:
  * 支持格式最多 (40+)
  * 转换质量高
  * Markdown 输出很好
- **缺点**:
  * 需要系统安装 pandoc
  * 不是纯 Python 解决方案

## 推荐方案

### 当前方案 (python-docx) - ✅ 合理
**适用场景**: 简单到中等复杂度的 DOCX 文档

**优点**:
- 已在项目依赖中
- 足够满足大多数场景
- 代码简单可维护
- 我们的智能分组逻辑已经弥补了结构不足

**改进建议**:
1. ✅ 已实现: 智能表格分组
2. 可选: 添加列表识别 (List 样式)
3. 可选: 添加图片说明提取

### 升级方案 1: mammoth (更好的格式保留)
```python
import mammoth

result = mammoth.convert_to_markdown(docx_path)
markdown_content = result.value
```

**优点**:
- 更好的标题检测
- 列表、粗体、斜体等格式保留
- 输出更接近原始文档结构

**缺点**:
- 增加一个依赖
- 需要测试与现有逻辑的兼容性

### 升级方案 2: Unstructured (企业级)
```python
from unstructured.partition.docx import partition_docx

elements = partition_docx(docx_path)
# 自动识别 Title, NarrativeText, Table 等
```

**优点**:
- 自动元素类型检测
- 支持更多格式
- 未来扩展性强

**缺点**:
- 依赖重 (>100MB)
- 可能 overkill 对于当前需求

## 结论

**推荐保持当前方案 (python-docx + 智能分组)**:
1. 已经解决了主要问题（大表格分组）
2. 代码简洁可维护
3. 依赖轻量
4. 对于 PageIndex 的 Markdown 处理足够

**如果遇到以下情况再考虑升级**:
- 需要处理复杂嵌套列表
- 需要提取图片和说明
- 需要支持更多文档格式 (HTML, RTF, 等)
- 需要更精确的样式检测

**下一步行动**:
- 无需修改，当前实现已经很好 ✅
- 可选: 记录到文档中供将来参考
