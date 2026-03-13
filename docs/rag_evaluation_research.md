# RAG 评估方法与框架研究报告

> **文档用途**: 为 PageIndex API Service 集成 LightRAG/HiRAG 提供评估策略与实施指导  
> **研究时间**: 2025-03-13  
> **研究范围**: 2024-2025 年社区主流 RAG 评估框架、指标体系和最佳实践

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [RAG 评估框架全景图](#2-rag-评估框架全景图)
3. [核心评估指标体系](#3-核心评估指标体系)
4. [LLM-as-a-Judge 方法](#4-llm-as-a-judge-方法)
5. [GraphRAG/LightRAG/HiRAG 特定评估](#5-graphraglightraghirag-特定评估)
6. [黄金数据集构建](#6-黄金数据集构建)
7. [推荐评估架构](#7-推荐评估架构)
8. [关键评估指标优先级](#8-关键评估指标优先级)
9. [最新基准数据集](#9-最新基准数据集)
10. [实施建议与 Roadmap](#10-实施建议与-roadmap)
11. [关键参考资料](#11-关键参考资料)

---

## 1. 执行摘要

### 1.1 研究背景

PageIndex API Service 当前采用 Format-Adaptive RAG 架构，但在多文档检索场景下存在局限性：

- **PageIndex 设计哲学**: 单文档优化，准确性优先，顺序 LLM 调用延迟高
- **问题**: Global Search 需要 LLM 遍历所有文档摘要，不适合 >5 文档场景
- **解决方案**: 引入 LightRAG/HiRAG 的图增强检索能力

### 1.2 核心发现

| 发现 | 影响 |
|------|------|
| **2024-2025 年趋势**: LLM-as-a-Judge 成为评估标准 | 可大幅降低人工评估成本 |
| **Braintrust/DeepEval** 支持生产数据闭环 | 实现持续评估与自动改进 |
| **LightRAG**: <100 tokens/query vs GraphRAG 610K | 显著降低多文档检索成本 |
| **HiRAG**: 三层检索 + GMM 聚类 | 适合处理层次化文档结构 |

### 1.3 关键决策点

1. **评估框架选择**: DeepEval (CI/CD 友好) + Braintrust (生产闭环)
2. **核心指标**: Answer Correctness + Context Relevance + Faithfulness
3. **对比维度**: 答案质量、检索延迟、Token 成本、可解释性

---

## 2. RAG 评估框架全景图

### 2.1 五大主流工具对比 (2025)

| 工具 | 类型 | 核心优势 | 适用场景 | 社区评分 |
|------|------|---------|---------|---------|
| **Braintrust** | 商业平台 | 生产-评估闭环、CI/CD 集成、80x 查询性能 | 生产级 RAG 持续改进 | 92/100 |
| **LangSmith** | 商业平台 | LangChain 生态无缝集成 | LangChain 应用观测 | 81/100 |
| **Arize Phoenix** | 开源+商业 | OpenTelemetry 标准、框架无关 | 多语言/框架可观测性 | 79/100 |
| **RAGAS** | 开源 | 无参考评估、学术标准、20+ 指标 | 研究/自定义评估基础设施 | 78/100 |
| **DeepEval** | 开源 | Pytest 集成、50+ 指标、CI/CD 友好 | 测试驱动开发 | 76/100 |

### 2.2 框架选型决策矩阵

```
                    开发阶段
              原型/POC    生产部署    企业级
            ┌─────────┬─────────┬─────────┐
    低成本  │ RAGAS   │ DeepEval│ Arize   │
            │ (开源)  │ (开源)  │ Phoenix │
            ├─────────┼─────────┼─────────┤
    高性能  │ RAGAS   │ Brain-  │ Brain-  │
            │ + 自建  │ trust   │ trust   │
            ├─────────┼─────────┼─────────┤
    全功能  │ RAGAS   │ Lang-   │ 混合    │
            │ + 自建  │ Smith   │ 方案    │
            └─────────┴─────────┴─────────┘
```

### 2.3 针对本项目的推荐

| 阶段 | 推荐工具 | 理由 |
|------|---------|------|
| **快速验证** | RAGAS | 开源、即开即用、无需复杂配置 |
| **CI/CD 集成** | DeepEval | Pytest 原生支持、测试驱动开发 |
| **生产监控** | Braintrust | 生产数据自动回流、持续改进 |
| **备选方案** | Arize Phoenix | 开源、OpenTelemetry 标准、LangChain 无关 |

---

## 3. 核心评估指标体系

### 3.1 检索组件评估 (Retriever Evaluation)

#### 3.1.1 上下文有效性指标

| 指标 | 定义 | 计算公式 | 适用场景 |
|------|------|---------|---------|
| **Context Relevance** | 检索结果中与查询相关的比例 | `相关语句数 / 总语句数` | 评估检索质量 |
| **Context Sufficiency** | 是否包含回答所需全部信息 | 与黄金标准对比 | 评估召回率 |
| **Context Precision@K** | Top-K 结果中相关文档比例 | `Top-K 相关文档 / K` | 评估排序质量 |
| **Context Recall** | 相关文档被检索到的比例 | `检索到的相关文档 / 总相关文档` | 评估覆盖度 |

#### 3.1.2 传统 IR 指标

| 指标 | 说明 | 适用场景 |
|------|------|---------|
| **Recall@K** | K 个结果中召回的相关文档比例 | 关注覆盖率 |
| **Precision@K** | K 个结果中精确率 | 关注准确性 |
| **F1@K** | Precision 和 Recall 的调和平均 | 平衡指标 |
| **MRR** | Mean Reciprocal Rank，首个正确答案排名的倒数平均 | 关注首位结果 |
| **NDCG@K** | 考虑位置的相关性折扣累积增益 | 关注排序质量 |
| **MAP** | Mean Average Precision，平均精确率 | 综合排序质量 |

### 3.2 生成组件评估 (Generator Evaluation)

#### 3.2.1 答案质量指标

| 指标 | 定义 | 评估方式 |
|------|------|---------|
| **Answer Relevance** | 答案是否直接回应用户查询 | LLM-as-Judge |
| **Answer Correctness** | 与黄金标准答案的事实一致性 | EM/F1/LLM-as-Judge |
| **Faithfulness** | 答案是否忠实于检索上下文 | 支持陈述数 / 总陈述数 |
| **Hallucination Rate** | 幻觉/虚构内容比例 | 1 - Faithfulness |

#### 3.2.2 细粒度指标

| 指标 | 说明 | 适用场景 |
|------|------|---------|
| **Answer Similarity** | 答案与参考答案的语义相似度 | 有标准答案时 |
| **Answer Completeness** | 答案覆盖用户问题的完整程度 | 开放域 QA |
| **Answer Conciseness** | 答案简洁程度（避免冗余） | 用户体验优化 |
| **Citation Precision** | 引用来源的准确性 | 可溯源性要求 |
| **Citation Recall** | 相关来源被引用的完整性 | 学术/法律场景 |

---

## 4. LLM-as-a-Judge 方法

### 4.1 RAG Triad 评估框架

```
                    RAG Triad
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ Context │   │ Ground- │   │ Answer  │
   │Relevance│   │ edness  │   │Relevance│
   └─────────┘   └─────────┘   └─────────┘
        │              │              │
        └──────────────┴──────────────┘
                       │
                    综合评估
```

### 4.2 评估提示词模板

#### 4.2.1 Context Relevance (上下文相关性)

```python
CONTEXT_RELEVANCE_PROMPT = """
评估以下检索到的上下文是否与用户查询相关。

用户查询: {query}
检索上下文: {context}

请评估:
1. 上下文中与查询直接相关的语句比例
2. 上下文是否包含回答查询所需的关键信息

评分标准:
- 1.0: 完全相关，所有信息都直接支持回答查询
- 0.7: 大部分相关，包含关键信息但有少量无关内容
- 0.4: 部分相关，包含一些有用信息但有大量无关内容
- 0.0: 完全不相关

请以 JSON 格式返回:
{
    "score": float,
    "reasoning": str,
    "relevant_statements": [str],
    "irrelevant_statements": [str]
}
"""
```

#### 4.2.2 Faithfulness (忠实度/幻觉检测)

```python
FAITHFULNESS_PROMPT = """
检查答案中的每个陈述是否都能在检索上下文中找到支持。

检索上下文: {context}
生成的答案: {answer}

请:
1. 提取答案中的所有事实陈述
2. 对每个陈述，判断是否能从上下文中找到支持
3. 计算忠实度分数

评分标准:
- 忠实度 = 支持陈述数 / 总陈述数

请以 JSON 格式返回:
{
    "score": float,
    "reasoning": str,
    "supported_statements": [{"statement": str, "evidence": str}],
    "unsupported_statements": [{"statement": str, "reason": str}]
}
"""
```

#### 4.2.3 Answer Relevance (答案相关性)

```python
ANSWER_RELEVANCE_PROMPT = """
评估答案是否直接且完整地回答了用户问题。

用户查询: {query}
生成的答案: {answer}

请评估:
1. 答案是否直接回应了查询的核心意图
2. 答案是否完整覆盖了查询的所有方面
3. 答案是否包含无关或冗余信息

评分标准:
- 1.0: 完美回答，直接、完整、无冗余
- 0.7: 较好回答，基本完整但有轻微冗余
- 0.4: 部分回答，遗漏了一些方面
- 0.0: 完全不相关

请以 JSON 格式返回:
{
    "score": float,
    "reasoning": str,
    "strengths": [str],
    "weaknesses": [str]
}
"""
```

### 4.3 高级评估技术

| 技术 | 说明 | 推荐工具 |
|------|------|---------|
| **G-Eval** | 使用 CoT 提示进行细致评估 | 自定义实现 |
| **Self-Consistency** | 多次采样取平均 | RAGAS |
| **Pairwise Comparison** | 两两比较排序 | Braintrust |
| **Reference-based** | 与黄金标准对比 | DeepEval |
| **Reference-free** | 无需参考答案 | RAGAS |

---

## 5. GraphRAG/LightRAG/HiRAG 特定评估

### 5.1 图 RAG 特有挑战

```
┌─────────────────────────────────────────────────────────────────┐
│                    图 RAG 评估挑战                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 多层次检索评估                                              │
│     - 实体级检索 vs 社区/主题级检索                             │
│     - 需要评估不同层级的贡献                                    │
│                                                                  │
│  2. 关系理解评估                                                │
│     - 答案是否正确利用了实体关系                                │
│     - 多跳推理的准确性                                          │
│                                                                  │
│  3. 全局 vs 局部搜索评估                                        │
│     - 全局搜索：聚合信息的完整性                                │
│     - 局部搜索：特定实体的精确性                                │
│                                                                  │
│  4. 图构建质量                                                  │
│     - 实体提取准确性                                            │
│     - 关系抽取完整性                                            │
│     - 社区检测质量                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 LightRAG 评估方法

#### 5.2.1 LightRAG 论文评估指标

| 指标 | 定义 | 评估方式 |
|------|------|---------|
| **Comprehensiveness** | 答案覆盖所有相关方面的程度 | LLM-as-Judge (0-100) |
| **Diversity** | 答案提供不同视角的丰富程度 | LLM-as-Judge (0-100) |
| **Empowerment** | 答案帮助用户理解并做出判断的能力 | LLM-as-Judge (0-100) |
| **Overall** | 综合质量评分 | LLM-as-Judge (0-100) |
| **Win Rate** | 两两比较的胜率 | 相对评估 |

#### 5.2.2 LightRAG 双层检索评估

```python
LIGHT_RAG_RETRIEVAL_METRICS = {
    "low_level": {
        "entity_retrieval_recall": "相关实体被检索的比例",
        "entity_retrieval_precision": "检索实体中相关的比例",
        "relation_retrieval_recall": "相关关系被检索的比例",
    },
    "high_level": {
        "theme_coverage": "答案覆盖的主题比例",
        "theme_diversity": "答案主题多样性",
        "global_context_utilization": "全局上下文利用程度",
    },
    "efficiency": {
        "tokens_per_query": "每查询使用的 token 数",
        "retrieval_latency_ms": "检索延迟（毫秒）",
        "index_build_time": "索引构建时间",
    }
}
```

### 5.3 HiRAG 评估方法

#### 5.3.1 HiRAG 三层检索架构

```
HiRAG Hierarchical Retrieval:

Level 3: Root Node (全局摘要层)
    │
    ▼
Level 2: Summary Entities (摘要实体层)
    │
    ▼
Level 1: Original Text Chunks (原始文本层)

评估需分别测试：
- 纯 Level 3：全局查询
- Level 3+2：中等粒度查询
- Level 3+2+1：详细查询
```

#### 5.3.2 HiRAG 论文评估指标

| 任务类型 | 指标 | 说明 |
|---------|------|------|
| **QFS** | Comprehensiveness | 查询聚焦摘要的完整性 |
| **QFS** | Diversity | 摘要视角多样性 |
| **QFS** | Empowerment | 用户决策支持度 |
| **MHQA** | EM (Exact Match) | 精确匹配率 |
| **MHQA** | F1 Score | 精确率和召回率的调和平均 |

### 5.4 GraphRAG-Bench 专用基准

#### 5.4.1 评估维度

| 维度 | 任务类型 | 说明 |
|------|---------|------|
| **Fact Retrieval** | 单选题、多选题 | 测试事实检索准确性 |
| **Complex Reasoning** | 多选题、填空题 | 测试多跳推理能力 |
| **Contextual Understanding** | 判断题、开放式 | 测试上下文理解深度 |

#### 5.4.2 覆盖领域

- Agriculture (农业)
- Computer Science (计算机科学)
- Legal (法律)
- Mixed Domain (混合领域)
- 共 16 个学科领域

### 5.5 针对 PageIndex 的对比评估维度

```
┌─────────────────────────────────────────────────────────────────┐
│           PageIndex vs LightRAG/HiRAG 对比评估                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  维度 1: 单文档深度检索                                         │
│  • PageIndex: 树结构推理优势                                    │
│  • LightRAG/HiRAG: 实体关系图                                   │
│  • 评估: 复杂条件查询的准确性                                   │
│                                                                  │
│  维度 2: 多文档聚合检索                                         │
│  • PageIndex: Global Search 延迟高                              │
│  • LightRAG/HiRAG: 图遍历优势                                   │
│  • 评估: 跨文档信息整合能力                                     │
│                                                                  │
│  维度 3: 增量更新能力                                           │
│  • PageIndex: 需重新处理整个文档                                │
│  • LightRAG: 支持增量更新                                       │
│  • 评估: 新文档加入后的索引更新效率                             │
│                                                                  │
│  维度 4: 成本效率                                               │
│  • PageIndex: 顺序 LLM 调用                                     │
│  • LightRAG: <100 tokens/query                                  │
│  • 评估: Token 消耗、API 调用成本                               │
│                                                                  │
│  维度 5: 可解释性                                               │
│  • PageIndex: 树路径可追溯                                      │
│  • LightRAG/HiRAG: 图路径可追溯                                 │
│  • 评估: 答案来源的清晰度                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 黄金数据集构建

### 6.1 构建流程

```
步骤 1: 定义评估范围和目标
    ├── 确定文档领域和类型
    ├── 定义查询类型分布（事实型、推理型、聚合型）
    └── 设定评估指标权重
    
    ↓
    
步骤 2: 收集真实用户查询（生产日志）
    ├── 从生产环境抽取真实查询
    ├── 分类和去重
    └── 匿名化处理
    
    ↓
    
步骤 3: 合成数据生成（补充边缘案例）
    ├── 使用 LLM 基于文档生成 QA 对
    ├── 人工审核和修正
    └── 确保分布均衡
    
    ↓
    
步骤 4: 人工验证与标注
    ├── 领域专家验证答案正确性
    ├── 多轮审核确保质量
    └── 解决歧义和争议
    
    ↓
    
步骤 5: 版本控制与演化
    ├── Golden Dataset v1.0 发布
    ├── 生产失败案例自动回流
    └── 定期更新和版本迭代
```

### 6.2 合成数据生成方法

#### 6.2.1 基于 RAGAS 的生成

```python
from ragas.testset import TestsetGenerator
from ragas.testset.evolutions import simple, reasoning, multi_context

# 配置生成器
generator = TestsetGenerator.from_default(
    generator_llm="gpt-4",
    critic_llm="gpt-4",
    embeddings="text-embedding-3-large"
)

# 定义演化策略
distributions = {
    simple: 0.5,           # 50% 简单事实查询
    reasoning: 0.3,        # 30% 推理查询
    multi_context: 0.2,    # 20% 多上下文查询
}

# 生成测试集
testset = generator.generate_with_langchain_docs(
    documents=documents,
    test_size=100,
    distributions=distributions,
    with_debugging_logs=True,
    raise_exceptions=False
)
```

#### 6.2.2 基于 DeepEval 的生成

```python
from deepeval.synthesizer import Synthesizer

# 配置合成器
synthesizer = Synthesizer(model="gpt-4")

# 生成 QA 对
goldens = synthesizer.generate_goldens_from_docs(
    document_paths=["doc1.pdf", "doc2.pdf"],
    max_goldens_per_document=20,
    num_evolutions=2,  # 演化次数（增加复杂度）
    enable_breadth_evolve=True,  # 广度演化
)

# 保存测试集
synthesizer.save_as(file_type="json", directory="./goldens")
```

#### 6.2.3 多跳问题生成 (MultiHop-RAG)

```python
MULTIHOP_GENERATION_TEMPLATE = """
基于以下多个文档片段，生成需要跨文档推理才能回答的问题。

文档片段 1: {doc1}
文档片段 2: {doc2}

请生成:
1. 一个需要结合两个文档信息才能回答的问题
2. 正确答案
3. 推理路径（说明如何从两个文档中得出答案）
4. 问题类型（bridge/comparison/others）

输出格式:
{
    "question": str,
    "answer": str,
    "reasoning_chain": [str],
    "type": str
}
"""
```

### 6.3 数据集质量控制

| 检查项 | 方法 | 标准 |
|--------|------|------|
| **答案正确性** | 人工审核 | 100% 准确率 |
| **问题清晰度** | LLM 评估 | 明确无歧义 |
| **答案完整性** | 专家评估 | 覆盖所有方面 |
| **难度分布** | 自动分析 | 简单:中等:困难 = 4:4:2 |
| **领域覆盖** | 统计分析 | 覆盖所有目标领域 |
| **避免泄露** | 文本匹配 | 答案不直接出现在问题中 |

### 6.4 版本管理

```
golden_datasets/
├── v1.0/
│   ├── train.json          # 训练集（用于few-shot）
│   ├── test.json           # 测试集
│   ├── validation.json     # 验证集
│   └── metadata.json       # 版本信息、统计指标
├── v1.1/
│   ├── ...
│   └── changelog.md        # 版本变更说明
└── latest -> v1.1/         # 软链接指向最新版本
```

---

## 7. 推荐评估架构

### 7.1 整体架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                      RAG 评估架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  离线评估   │    │  在线评估   │    │  对比实验   │         │
│  │  (CI/CD)    │◄──►│  (生产)     │◄──►│  (A/B Test) │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│         │                  │                  │                │
│         ▼                  ▼                  ▼                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ DeepEval    │    │ Braintrust  │    │ 自定义脚本   │         │
│  │ + Pytest    │    │ / Arize     │    │ + LLM Judge │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│         │                  │                  │                │
│         └──────────────────┼──────────────────┘                │
│                            ▼                                   │
│                   ┌─────────────────┐                          │
│                   │  评估指标存储    │                          │
│                   │  (SQLite/JSON)  │                          │
│                   └────────┬────────┘                          │
│                            │                                   │
│                            ▼                                   │
│                   ┌─────────────────┐                          │
│                   │  可视化与报告    │                          │
│                   │  (Dashboard)    │                          │
│                   └─────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 离线评估 (CI/CD 阶段)

#### 7.2.1 DeepEval + Pytest 集成

```python
# tests/test_rag_pipeline.py
import pytest
from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRelevancyMetric
)
from deepeval.test_case import LLMTestCase

# 定义评估指标
answer_relevancy = AnswerRelevancyMetric(threshold=0.7)
faithfulness = FaithfulnessMetric(threshold=0.7)
context_relevancy = ContextualRelevancyMetric(threshold=0.6)

class TestRAGPipeline:
    
    @pytest.mark.parametrize("test_case", load_golden_dataset())
    def test_rag_quality(self, test_case):
        """测试 RAG 流水线质量"""
        # 执行检索和生成
        result = rag_pipeline.query(test_case["query"])
        
        # 创建测试用例
        llm_test_case = LLMTestCase(
            input=test_case["query"],
            actual_output=result["answer"],
            expected_output=test_case["expected_answer"],
            retrieval_context=result["retrieved_contexts"]
        )
        
        # 断言测试
        assert_test(
            llm_test_case,
            metrics=[answer_relevancy, faithfulness, context_relevancy]
        )
    
    def test_retrieval_latency(self):
        """测试检索延迟"""
        import time
        start = time.time()
        result = rag_pipeline.query("测试查询")
        latency = time.time() - start
        
        assert latency < 5.0, f"检索延迟 {latency}s 超过阈值 5s"
```

#### 7.2.2 GitHub Actions 集成

```yaml
# .github/workflows/rag-eval.yml
name: RAG Evaluation

on:
  pull_request:
    paths:
      - 'services/**'
      - 'models/**'
  push:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install uv
        run: pip install uv
      
      - name: Install dependencies
        run: uv sync
      
      - name: Run RAG evaluation
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          uv run pytest tests/test_rag_pipeline.py \
            --cov=services \
            --cov-report=xml \
            --html=report.html
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
      
      - name: Comment PR
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('report.html', 'utf8');
            // 提取关键指标并评论到 PR
```

### 7.3 在线评估 (生产环境)

#### 7.3.1 Braintrust 集成

```python
# services/evaluation.py
from braintrust import Eval, traced
import asyncio

class ProductionEvaluator:
    def __init__(self):
        self.evaluator = Eval(
            project="pageindex-rag",
            experiment_name="production-v1"
        )
    
    @traced
    async def evaluate_query(self, query: str, result: dict):
        """评估单次查询"""
        
        # 记录检索结果
        self.evaluator.log({
            "input": query,
            "output": result["answer"],
            "metadata": {
                "retrieved_docs": result["sources"],
                "latency_ms": result["latency"],
                "tokens_used": result["token_usage"]
            }
        })
        
        # 异步评估质量
        scores = await self._compute_scores(query, result)
        return scores
    
    async def _compute_scores(self, query: str, result: dict):
        """计算评估分数"""
        scores = {}
        
        # Context Relevance
        scores["context_relevance"] = await self._eval_context_relevance(
            query, result["retrieved_contexts"]
        )
        
        # Answer Relevance (需要用户反馈或 LLM 评估)
        scores["answer_relevance"] = await self._eval_answer_relevance(
            query, result["answer"]
        )
        
        return scores
```

#### 7.3.2 用户反馈收集

```python
# 在 API 响应中收集反馈
class FeedbackCollector:
    async def collect_feedback(
        self,
        query_id: str,
        rating: int,  # 1-5 星
        feedback_type: str,  # "helpful", "not_helpful", "partial"
        comment: Optional[str] = None
    ):
        """收集用户反馈并关联到查询记录"""
        
        feedback_record = {
            "query_id": query_id,
            "rating": rating,
            "type": feedback_type,
            "comment": comment,
            "timestamp": datetime.utcnow()
        }
        
        # 存储到数据库
        await self.db.feedback.insert_one(feedback_record)
        
        # 低分反馈自动加入测试集候选
        if rating <= 2:
            await self._flag_for_review(query_id)
```

### 7.4 对比实验 (A/B Test)

```python
# experiments/compare_rag_systems.py
import asyncio
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ComparisonResult:
    system_name: str
    metrics: Dict[str, float]
    latency_ms: float
    cost_per_query: float

class RAGComparator:
    def __init__(self):
        self.systems = {
            "pageindex": PageIndexRAG(),
            "lightrag": LightRAG(),
            "hirag": HiRAG(),
            "hybrid": HybridRAG()
        }
    
    async def compare(
        self,
        test_queries: List[str],
        judge_llm: str = "gpt-4"
    ) -> Dict[str, ComparisonResult]:
        """对比多个 RAG 系统"""
        
        results = {}
        
        for name, system in self.systems.items():
            print(f"评估系统: {name}")
            
            system_results = []
            latencies = []
            costs = []
            
            for query in test_queries:
                start = time.time()
                result = await system.query(query)
                latency = (time.time() - start) * 1000
                
                system_results.append({
                    "query": query,
                    "answer": result["answer"],
                    "contexts": result["contexts"]
                })
                latencies.append(latency)
                costs.append(result.get("cost", 0))
            
            # 计算指标
            metrics = await self._evaluate_with_judge(
                system_results, judge_llm
            )
            
            results[name] = ComparisonResult(
                system_name=name,
                metrics=metrics,
                latency_ms=sum(latencies) / len(latencies),
                cost_per_query=sum(costs) / len(costs)
            )
        
        return results
    
    async def _evaluate_with_judge(
        self,
        results: List[Dict],
        judge_llm: str
    ) -> Dict[str, float]:
        """使用 LLM-as-Judge 评估结果"""
        # 实现评估逻辑
        pass
```

---

## 8. 关键评估指标优先级

### 8.1 指标优先级矩阵

| 优先级 | 指标 | 理由 | 阈值建议 |
|--------|------|------|---------|
| **P0 - 关键** | Answer Correctness | 最终答案正确性是最核心指标 | > 0.8 |
| **P0 - 关键** | Context Relevance | 检索质量直接影响生成质量 | > 0.7 |
| **P0 - 关键** | Latency | 用户体验核心指标 | < 3s |
| **P1 - 重要** | Faithfulness/Hallucination | 高风险场景（金融/法律）必需 | > 0.85 |
| **P1 - 重要** | Answer Completeness | 确保答案覆盖用户问题 | > 0.75 |
| **P1 - 重要** | Cost per Query | 商业化考量 | < $0.1 |
| **P2 - 优化** | Comprehensiveness | 复杂查询场景重要 | > 0.7 |
| **P2 - 优化** | Diversity | 多视角答案质量 | > 0.6 |
| **P2 - 优化** | Citation Accuracy | 可解释性和溯源 | > 0.9 |
| **P3 - 监控** | Token Usage | 成本优化参考 | 监控趋势 |

### 8.2 场景化指标权重

#### 8.2.1 金融文档分析场景

```python
FINANCE_DOMAIN_WEIGHTS = {
    "answer_correctness": 0.30,    # 准确性最重要
    "faithfulness": 0.25,          # 避免幻觉
    "citation_accuracy": 0.20,     # 可溯源
    "context_relevance": 0.15,     # 检索质量
    "latency": 0.10,               # 实时性相对次要
}
```

#### 8.2.2 客服问答场景

```python
CUSTOMER_SERVICE_WEIGHTS = {
    "latency": 0.25,               # 实时响应重要
    "answer_relevance": 0.20,      # 直接回答
    "answer_correctness": 0.20,    # 准确性
    "context_relevance": 0.15,     # 检索质量
    "tone_friendly": 0.10,         # 语气友好
    "conciseness": 0.10,           # 简洁明了
}
```

#### 8.2.3 研究分析场景

```python
RESEARCH_DOMAIN_WEIGHTS = {
    "comprehensiveness": 0.25,     # 全面性
    "diversity": 0.20,             # 多角度
    "answer_correctness": 0.20,    # 准确性
    "citation_recall": 0.15,       # 引用完整
    "faithfulness": 0.10,          # 忠实原文
    "context_relevance": 0.10,     # 检索质量
}
```

---

## 9. 最新基准数据集

### 9.1 通用 RAG 基准

| 数据集 | 类型 | 规模 | 特点 | 适用评估 |
|--------|------|------|------|---------|
| **HotpotQA** | 多跳 QA | 113K | 经典基准，需要跨段落推理 | 基础能力验证 |
| **Natural Questions** | 开放域 QA | 323K | Google 搜索查询 | 真实场景模拟 |
| **MS MARCO** | 段落排序 | 1M+ | 微软搜索日志 | 检索质量评估 |
| **TriviaQA** | 阅读理解 | 650K | 琐事问答 | 细粒度理解 |
| **SQuAD 2.0** | 阅读理解 | 150K | 包含无法回答的问题 | 拒答能力评估 |

### 9.2 GraphRAG 专用基准

| 数据集 | 类型 | 特点 | 适用系统 |
|--------|------|------|---------|
| **GraphRAG-Bench** | 综合 | 16 学科，多题型 | GraphRAG/LightRAG/HiRAG |
| **MultiHop-RAG** | 多跳 QA | 跨文档推理，需要实体链接 | LightRAG |
| **2WikiMultiHopQA** | 多跳 QA | 维基百科实体推理 | GraphRAG |
| **ComplexWebQuestions** | 多跳 QA | 复杂网络查询 | 高级检索系统 |

### 9.3 领域特定基准

| 数据集 | 领域 | 规模 | 特点 |
|--------|------|------|------|
| **FinanceBench** | 金融 | 10K | 财报分析问题 |
| **PubMedQA** | 医学 | 1K | 生物医学问答 |
| **SCIQ** | 科学 | 13.7K | 科学概念问题 |
| **ARC** | 科学 | 7.8K | 科学推理挑战 |
| **LegalBench** | 法律 | - | 法律任务集合 |

### 9.4 评估挑战基准

| 基准 | 挑战类型 | 说明 |
|------|---------|------|
| **CRAG** | 动态事实 | 测试处理时效性信息的能力 |
| **RAGBench** | 多领域 | 10+ 领域，TRACe 指标 |
| **RAGTruth** | 幻觉检测 | 专门用于检测 RAG 幻觉 |
| **DomainRAG** | 领域适应 | 跨领域泛化能力 |

---

## 10. 实施建议与 Roadmap

### 10.1 三阶段实施计划

#### 阶段一：基础建设（1-2 周）

**目标**: 建立基础评估能力

| 任务 | 交付物 | 负责人 |
|------|--------|--------|
| 集成 RAGAS | `evaluation/ragas_eval.py` | - |
| 构建初始黄金数据集 (50 QA 对) | `data/golden/v1.0/` | - |
| 实现三大核心指标 | Context Relevance, Faithfulness, Answer Relevance | - |
| 建立评估脚本 | `scripts/evaluate.py` | - |

**验收标准**:
- 能够运行单次评估并输出分数
- 黄金数据集覆盖简单/推理/聚合三类查询
- 评估脚本支持命令行调用

#### 阶段二：CI/CD 集成（2-4 周）

**目标**: 将评估集成到开发流程

| 任务 | 交付物 | 备注 |
|------|--------|------|
| 集成 DeepEval | `tests/test_rag.py` | Pytest 兼容 |
| GitHub Actions 工作流 | `.github/workflows/eval.yml` | PR 自动评估 |
| 扩展黄金数据集到 200+ QA | `data/golden/v2.0/` | 包含多跳问题 |
| 实现对比评估框架 | `experiments/compare.py` | 支持 A/B 测试 |

**验收标准**:
- 每次 PR 自动运行评估测试
- 评估失败阻塞合并
- 能够对比 PageIndex vs LightRAG 效果

#### 阶段三：生产闭环（1-2 月）

**目标**: 建立持续改进机制

| 任务 | 交付物 | 备注 |
|------|--------|------|
| 集成 Braintrust/Arize | `services/evaluation.py` | 生产监控 |
| 用户反馈收集系统 | Feedback API + UI | 评分 + 评论 |
| 失败案例自动回流 | `scripts/feedback_to_golden.py` | 测试集自动更新 |
| 评估 Dashboard | Streamlit/Dash 应用 | 可视化指标 |

**验收标准**:
- 生产查询 100% 记录和评估
- 用户反馈实时影响模型迭代
- 黄金数据集月度自动更新

### 10.2 LightRAG/HiRAG 集成评估 Roadmap

```
Week 1-2: 技术预研
├── 部署 LightRAG 和 HiRAG 测试环境
├── 准备对比评估数据集（多文档场景）
└── 设计对比实验方案

Week 3-4: 原型验证
├── 实现 LightRAG 集成原型
├── 运行对比实验（PageIndex vs LightRAG）
├── 收集性能和质量数据
└── 撰写技术评估报告

Week 5-6: 决策与规划
├── 基于评估结果决定集成方案
├── 设计混合架构（如果需要）
├── 制定详细实施计划
└── 资源和时间估算

Week 7-12: 实施与优化
├── 生产级集成开发
├── 持续评估和调优
├── 性能优化
└── 文档和培训
```

### 10.3 关键决策点

| 决策点 | 时间 | 输入 | 输出 |
|--------|------|------|------|
| **评估框架选择** | Week 1 | 工具调研报告 | DeepEval + Braintrust |
| **黄金数据集规模** | Week 2 | 初步实验结果 | 200 QA 对（V2.0） |
| **LightRAG 可行性** | Week 4 | 对比实验数据 | Go/No-Go 决策 |
| **混合架构设计** | Week 6 | 技术评估报告 | 架构设计方案 |
| **生产上线** | Week 12 | 完整测试报告 | 上线检查清单 |

### 10.4 风险与缓解策略

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| **评估指标与人工判断不一致** | 高 | 引入人工标注校准，设置可调节阈值 |
| **黄金数据集偏差** | 中 | 多轮审核，包含边缘案例，定期更新 |
| **LLM-as-Judge 成本过高** | 中 | 使用轻量级模型（GPT-3.5）做初筛，GPT-4 做终审 |
| **LightRAG 效果不达预期** | 高 | 保留 PageIndex 回退机制，渐进式迁移 |
| **生产监控延迟** | 中 | 异步评估，采样策略，避免影响主流程 |

---

## 11. 关键参考资料

### 11.1 学术论文

| 论文 | 作者/年份 | 链接 | 核心贡献 |
|------|----------|------|---------|
| **RAG Evaluation Survey** | 2025 | [arXiv:2504.14891](https://arxiv.org/abs/2504.14891) | 最全面的 RAG 评估综述 |
| **LightRAG** | 2024 | [arXiv:2410.05779](https://arxiv.org/abs/2410.05779) | 双层检索，低成本高效 |
| **HiRAG** | 2025 | [arXiv:2503.10150](https://arxiv.org/abs/2503.10150) | 层次化知识索引 |
| **GraphRAG** | Microsoft | [论文](https://arxiv.org/abs/2404.16130) | 图增强检索生成 |
| **RAGAS** | 2023 | [arXiv:2309.15217](https://arxiv.org/abs/2309.15217) | 无参考评估框架 |

### 11.2 开源项目

| 项目 | 链接 | 用途 |
|------|------|------|
| **RAGAS** | [github.com/explodinggradients/ragas](https://github.com/explodinggradients/ragas) | 开源 RAG 评估 |
| **DeepEval** | [github.com/confident-ai/deepeval](https://github.com/confident-ai/deepeval) | 单元测试式评估 |
| **LightRAG** | [github.com/SylphAI-Inc/LightRAG](https://github.com/SylphAI-Inc/LightRAG) | 轻量级图 RAG |
| **HiRAG** | [github.com/higraph-ai/HiRAG](https://github.com/higraph-ai/HiRAG) | 层次化图 RAG |
| **Arize Phoenix** | [github.com/Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | LLM 可观测性 |
| **GraphRAG-Bench** | [github.com/GraphRAG-Bench](https://github.com/GraphRAG-Bench) | 图 RAG 基准 |

### 11.3 评估数据集

| 数据集 | 链接 | 说明 |
|--------|------|------|
| **HotpotQA** | [hotpotqa.github.io](https://hotpotqa.github.io) | 多跳 QA 基准 |
| **CRAG** | [github.com/facebookresearch/CRAG](https://github.com/facebookresearch/CRAG) | 综合 RAG 基准 |
| **RAGBench** | [github.com/rag-benchmark/ragbench](https://github.com/rag-benchmark/ragbench) | 多领域 RAG 基准 |

### 11.4 商业平台文档

| 平台 | 文档链接 | 特点 |
|------|---------|------|
| **Braintrust** | [braintrust.dev/docs](https://www.braintrust.dev/docs) | 生产级评估平台 |
| **LangSmith** | [smith.langchain.com](https://smith.langchain.com) | LangChain 生态 |
| **Weights & Biases** | [wandb.ai](https://wandb.ai) | 实验追踪 |

### 11.5 技术博客与指南

| 标题 | 来源 | 链接 |
|------|------|------|
| Best RAG Evaluation Tools | Braintrust | [braintrust.dev/articles/best-rag-evaluation-tools](https://www.braintrust.dev/articles/best-rag-evaluation-tools) |
| RAG Evaluation Guide | RAGAS | [docs.ragas.io/en/latest/concepts/metrics/index.html](https://docs.ragas.io/en/latest/concepts/metrics/index.html) |
| Evaluating RAG Systems | DeepEval | [docs.confident-ai.com/docs/evaluation-introduction](https://docs.confident-ai.com/docs/evaluation-introduction) |

---

## 附录

### A. 术语表

| 术语 | 定义 |
|------|------|
| **RAG** | Retrieval-Augmented Generation，检索增强生成 |
| **GraphRAG** | 基于知识图的 RAG 系统 |
| **LightRAG** | 轻量级双层检索图 RAG |
| **HiRAG** | 层次化知识索引图 RAG |
| **LLM-as-Judge** | 使用 LLM 作为评估者 |
| **Golden Dataset** | 人工标注的高质量测试集 |
| **Context Relevance** | 检索上下文与查询的相关性 |
| **Faithfulness** | 答案忠实于检索上下文 |
| **Hallucination** | 模型生成虚构内容 |
| **Multi-hop QA** | 需要多步推理的问答 |

### B. 评估指标计算公式

```python
# Context Relevance
context_relevance = len(relevant_statements) / len(all_statements)

# Context Precision@K
context_precision_at_k = len(relevant_in_top_k) / k

# Context Recall
context_recall = len(retrieved_relevant) / len(all_relevant)

# Faithfulness
faithfulness = len(supported_statements) / len(all_statements)

# F1 Score
f1 = 2 * (precision * recall) / (precision + recall)

# MRR
mrr = sum(1 / rank_i for rank_i in ranks_of_first_relevant) / len(queries)

# NDCG
ndcg = dcg / ideal_dcg
where dcg = sum(relevance_i / log2(i + 1) for i in positions)
```

### C. 快速参考卡片

```
┌─────────────────────────────────────────────────────────────────┐
│                   RAG 评估快速参考                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  三大核心指标:                                                   │
│  1. Context Relevance  - 检索质量                               │
│  2. Faithfulness       - 避免幻觉                               │
│  3. Answer Correctness - 最终质量                               │
│                                                                  │
│  推荐工具组合:                                                   │
│  • 开发: RAGAS + DeepEval                                       │
│  • 生产: Braintrust / Arize Phoenix                             │
│                                                                  │
│  评估频率:                                                       │
│  • CI/CD: 每次 PR                                               │
│  • 回归: 每周                                                   │
│  • 全面: 每月                                                   │
│                                                                  │
│  黄金数据集规模:                                                 │
│  • 起步: 50 QA                                                  │
│  • 标准: 200 QA                                                 │
│  • 完善: 1000+ QA                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

*文档版本: 1.0*  
*最后更新: 2025-03-13*  
*维护者: PageIndex API Team*
