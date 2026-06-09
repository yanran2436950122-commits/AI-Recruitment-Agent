# 系统架构

本文档说明 AI Recruitment Agent 的系统架构、核心模块、数据流与设计原则。

AI Recruitment Agent 采用本地优先的分层架构，通过 Streamlit 提供交互界面，使用 LangGraph 编排多智能体工作流，并结合 RAG 知识库增强分析结果。

---

# 1. 架构目标

系统设计目标包括：

- 支持 Candidate 与 HR 两类使用场景
- 支持简历解析、岗位分析与匹配评估
- 支持多智能体工作流编排
- 支持知识库检索增强
- 支持历史记录、审计日志与运行监控
- 保持本地可运行、可调试、可验证

---

# 2. 整体架构

```text
┌──────────────────────────────────────────┐
│                用户层                    │
│                                          │
│   Candidate（求职者） / HR（招聘方）     │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│             Frontend Layer               │
│                                          │
│                Streamlit                 │
│                                          │
│ 简历上传 / 岗位管理 / 历史记录 / 监控中心 │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│              Service Layer               │
│                                          │
│ Analysis Service                         │
│ History Service                          │
│ File Service                             │
│ Monitoring Service                       │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│             Workflow Layer               │
│                                          │
│                LangGraph                 │
│                                          │
│        状态管理 / 节点调度 / 路由控制     │
└──────────────────┬───────────────────────┘
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Resume   │ │   JD     │ │ Matching │
│ Agent    │ │  Agent   │ │  Agent   │
└────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │
     └────────────┴────────────┘
                   │
                   ▼
          ┌────────────────┐
          │ Manager Agent  │
          └───────┬────────┘
                  │
                  ▼
┌──────────────────────────────────────────┐
│                RAG Layer                 │
│                                          │
│ Document Loader / Chunk Builder          │
│ Embedding / Similarity Search            │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│            Repository Layer              │
│                                          │
│ Analysis Repository                      │
│ Job Repository                           │
│ Audit Repository                         │
│ Monitoring Repository                    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│            Persistence Layer             │
│                                          │
│ SQLite / JSON Vector Store / File System │
└──────────────────────────────────────────┘
```

---

# 3. 分层说明

## 3.1 Frontend Layer

目录：

```text
frontend/
```

主要职责：

- 渲染 Streamlit 页面
- 接收用户上传文件
- 管理 Candidate / HR 身份切换
- 展示分析结果
- 展示历史记录
- 展示知识库状态
- 展示监控中心与审计日志

主要页面包括：

- 新建分析
- 历史分析
- 岗位管理 / 目标岗位管理
- 知识库
- 监控中心
- 调试信息

---

## 3.2 Service Layer

目录：

```text
services/
```

主要职责：

- 封装业务操作
- 调用工作流
- 处理文件生命周期
- 管理分析记录
- 对接存储与监控模块

该层用于减少前端页面与底层实现之间的直接耦合。

---

## 3.3 Workflow Layer

目录：

```text
graph/
```

主要职责：

- 定义 LangGraph 工作流
- 管理状态流转
- 编排 Agent 执行顺序
- 控制条件分支与异常处理

工作流负责将多个 Agent 的能力组合成完整的招聘分析流程。

---

## 3.4 Agent Layer

目录：

```text
agents/
```

系统通过多个 Agent 协同完成分析任务。

| Agent | 职责 |
|---|---|
| Resume Agent | 解析简历内容，提取候选人信息 |
| JD Agent | 解析岗位描述，提取岗位要求 |
| Matching Agent | 执行匹配评估、技能差距分析 |
| Manager Agent | 汇总结果，生成最终分析报告 |
| HR Manager Agent | 面向 HR 场景组织候选人评估流程 |

---

## 3.5 RAG Layer

目录：

```text
rag/
```

主要职责：

- 读取知识库文件
- 切分文档
- 构建向量记录
- 执行相似度检索
- 为分析结果提供上下文增强

知识库默认目录：

```text
data/knowledge_base/
```

向量库默认目录：

```text
data/vector_store/
```

---

## 3.6 Repository Layer

目录：

```text
repositories/
```

主要职责：

- 封装数据库读写
- 隔离业务逻辑与存储实现
- 管理分析记录、岗位、审计日志等数据访问

---

## 3.7 Persistence Layer

主要包括：

```text
SQLite
JSON Vector Store
Local File System
```

用途：

| 存储 | 用途 |
|---|---|
| SQLite | 分析记录、岗位信息、审计日志、运行记录 |
| JSON Vector Store | 本地知识库向量记录 |
| Local File System | 上传文件、知识库文件、导出报告 |

---

# 4. 业务流程

## 4.1 Candidate 分析流程

```text
创建目标岗位
    ↓
上传简历
    ↓
输入或选择岗位需求
    ↓
Resume Agent 解析简历
    ↓
JD Agent 解析岗位
    ↓
Matching Agent 计算匹配结果
    ↓
RAG 检索补充上下文
    ↓
Manager Agent 汇总报告
    ↓
保存历史记录
```

---

## 4.2 HR 分析流程

```text
创建招聘岗位
    ↓
上传候选人简历
    ↓
Resume Agent 解析简历
    ↓
JD Agent 解析岗位
    ↓
Matching Agent 执行候选人评估
    ↓
RAG 检索补充上下文
    ↓
HR Manager Agent 生成评估报告
    ↓
保存历史记录
```

---

# 5. RAG 数据流

```text
知识库文件
    ↓
文档读取
    ↓
文本切分
    ↓
生成 Embedding
    ↓
写入 JSON Vector Store
    ↓
用户查询
    ↓
相似度检索
    ↓
返回上下文
    ↓
参与分析报告生成
```

---

# 6. 知识库去重机制

知识库导入支持重复执行。

为避免重复导入导致向量库持续膨胀，系统为每个知识块生成稳定的：

```text
chunk_id
```

生成依据：

```text
source
chunk_position
normalized_text
```

导入时：

```text
如果 chunk_id 已存在，则跳过
如果 chunk_id 不存在，则写入
```

预期结果：

首次导入：

```text
inserted > 0
skipped = 0
```

重复导入：

```text
inserted = 0
skipped > 0
```

该机制保证知识库导入具备幂等性。

---

# 7. 监控与审计架构

目录：

```text
monitoring/
memory/
```

系统提供基础可观测能力。

## 7.1 Run Log

记录工作流运行情况：

- run_id
- analysis_id
- actor_type
- workflow_name
- status
- duration_ms

---

## 7.2 Error Trace

记录异常与失败信息，用于定位：

- 节点失败
- 工具调用失败
- 模型调用失败
- 解析失败

---

## 7.3 Agent Metrics

记录 Agent 或节点执行指标：

- node_name
- average_duration
- total

---

## 7.4 RAG Metrics

记录检索相关指标：

- retrieval_count
- retrieval_hit_count
- retrieval_miss_count
- average_retrieval_time

---

## 7.5 LLM Metrics

记录模型调用相关指标：

- llm_calls
- llm_failures
- average_response_time
- fallback_calls

---

## 7.6 Audit Log

记录关键业务操作。

部分字段可能为空。

例如：

- Candidate 操作通常不包含 company_id
- HR 操作通常包含 company_id 或 job_id
- 非分析类操作可能不包含 analysis_id

字段为空不一定表示异常，应结合 action 与 actor_type 判断。

---

# 8. 文件生命周期

上传文件默认存储于：

```text
data/uploads/
```

系统会记录文件元数据，并支持：

- 上传
- 读取
- 下载
- 软删除
- 过期清理

导出报告默认存储于：

```text
exports/
```

---

# 9. 设计原则

## 9.1 本地优先

系统优先保证本地可运行。

当前版本不强依赖外部数据库、外部向量数据库或复杂基础设施。

---

## 9.2 可观测

系统运行过程应具备可追踪能力。

主要通过：

- Run Log
- Error Trace
- Metrics
- Audit Log

实现。

---

## 9.3 可扩展

当前架构保留扩展空间。

后续可扩展：

- PostgreSQL
- Redis
- Chroma / Qdrant
- 对象存储
- 用户认证
- 权限管理

---



# 10. 当前限制

当前系统更适合：

- 本地开发
- 原型验证
- 小规模知识库
- 单机运行

不适合作为：

- 高并发生产系统
- 公网多用户系统
- 大规模 ATS 系统

相关限制与排查建议请参考：

```text
docs/OPERATIONS.md
```
