# Hybrid RAG Constitution

本宪法定义了 Hybrid RAG 项目的核心开发原则和规范，所有开发活动必须遵循。

---

## Core Principles

### I. 双语工作规范 (Bilingual Working Standard)

**AI Agent 必须遵循以下语言使用规则：**

- **思考 (Think)**：使用英文进行问题分析、逻辑推理和内部思考
- **搜索 (Search)**：使用英文进行网络搜索、文档检索和资料查询
- **响应 (Response)**：使用中文向用户展示结果、解释和交互
- **写作 (Write)**：使用中文编写所有项目文档、注释和代码说明

**Rationale**:
- 英文搜索和思考能获取更广泛的全球技术资源和最佳实践
- 中文输出确保团队成员能够完全理解和参与
- 代码注释使用中文，符合项目现有实践

**Examples**:
```
✅ 正确：
  [思考] "Analyzing the API design pattern for async file uploads..."
  [搜索] "async file upload best practices python fastapi"
  [响应] "建议使用 BackgroundTasks 处理文件上传..."
  [写作] """使用 BackgroundTasks 实现异步文件处理，避免阻塞主线程。"""

❌ 错误：
  [响应] "I recommend using BackgroundTasks for file uploads..."
  [写作] """Use BackgroundTasks to handle async file processing."""
```

---

### II. 模块化优先 (Modularity First)

- 每个功能从独立的模块/服务开始设计
- 模块必须自包含、独立可测试、有清晰文档
- 明确的职责边界，避免仅用于组织的抽象层
- 遵循 Single Responsibility Principle

---

### III. 测试驱动开发 (Test-First - NON-NEGOTIABLE)

- **强制要求**：先写测试 → 用户确认 → 测试失败 → 实现代码
- 严格执行 Red-Green-Refactor 循环
- 单元测试和集成测试缺一不可
- 测试覆盖率作为代码审查的必要条件

---

### IV. API 契约优先 (API Contract First)

- 先定义 API 接口和响应格式，再实现逻辑
- 使用 Pydantic 模型严格定义数据结构
- API 变更必须保持向后兼容（Additive Changes）
- 所有 API 变更需要更新文档和测试

---

### V. 代码质量标准 (Code Quality Standards)

- **类型提示**：所有函数必须有完整的类型注解
- **Lint 规范**：ruff 检查 0 错误，遵循 Google Docstring 规范
- **代码审查**：所有 PR 必须通过审查，复杂度需要正当理由
- **文档要求**：公共 API 必须有中文文档字符串

---

## Development Workflow

### 1. 需求澄清阶段

- 使用 `/speckit.clarify` 识别和解决需求中的模糊点
- 记录所有澄清决策在 `clarifications.md`
- 确认验收标准后再进入设计阶段

### 2. 技术规划阶段

- 使用 `/speckit.plan` 制定详细技术方案
- 包含数据模型、API 设计、错误处理策略
- 评估性能影响和资源需求

### 3. 实现阶段

- 使用 `/speckit.tasks` 分解为可执行任务
- 优先实现测试用例
- 遵循双语规范编写代码和文档

### 4. 验证阶段

- 所有测试必须通过（单元测试 + 集成测试）
- 代码质量检查通过（ruff + mypy）
- API 契约符合设计规范

---

## Technology Stack

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 语言 | Python 3.13+ | 类型提示、异步支持 |
| Web 框架 | FastAPI | 自动生成文档、Pydantic 集成 |
| 数据库 | SQLite + SQLAlchemy | 轻量、异步支持 |
| 向量存储 | Qdrant (embedded) | Hybrid Search |
| RAG 后端 | PageIndex, LightRAG, HiRAG | 多策略检索 |
| 包管理 | uv | 快速、现代 |
| 代码质量 | ruff, mypy, pytest | 完整工具链 |

---

## Governance

### 宪法修订流程

1. **提案**：任何团队成员可提出修订建议
2. **讨论**：在团队内部讨论影响和必要性
3. **文档**：修订必须更新本文档并记录变更历史
4. **生效**：团队负责人批准后生效

### 合规检查

- 所有 PR 必须声明符合宪法规范
- 代码审查时检查语言使用规范
- 定期回顾宪法执行效果

---

## 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0.0 | 2025-03-15 | 初始版本，定义双语规范、开发流程、技术标准 |

---

**Version**: 1.0.0 | **Ratified**: 2025-03-15 | **Last Amended**: 2025-03-15
