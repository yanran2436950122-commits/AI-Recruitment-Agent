# AI Recruitment Agent

基于 LangGraph 的招聘场景多智能体工作流系统。

AI Recruitment Agent 面向招聘与求职场景构建，支持简历解析、岗位分析、候选人与岗位匹配评估、知识检索增强（RAG）、历史记录管理、审计日志与运行监控等能力。

项目采用 Streamlit + FastAPI 双入口架构，通过 LangGraph 编排多个 Agent 协同完成分析任务，并提供本地优先（Local-First）的部署方案。

---

# 项目定位

本项目旨在探索以下技术在招聘场景中的工程实践：

- 多智能体协作（Multi-Agent）
- 工作流编排（LangGraph）
- 检索增强生成（RAG）
- 可观测性（Observability）
- 审计追踪（Audit Log）
- AI 辅助软件开发

项目定位为：

```text
本地部署
原型验证
学习研究
工程实践
```

而非生产级 ATS（Applicant Tracking System）系统。

---

# 功能特性

## Candidate（求职者）

支持：

- 上传个人简历
- 创建目标岗位
- 获取岗位匹配分析
- 查看历史分析记录
- 获取职业发展建议
- 管理个人分析结果

---

## HR（招聘方）

支持：

- 创建招聘岗位
- 上传候选人简历
- 获取候选人评估报告
- 查看历史分析记录
- 管理岗位信息
- 管理候选人分析结果

---

## RAG 知识库

支持：

- 本地知识库导入
- 文档切分
- 向量化存储
- 相似度检索
- 上下文增强分析

支持格式：

- PDF
- DOCX

---

## 历史记录与审计

支持：

- 分析记录存储
- 历史查询
- 分析详情查看
- 操作审计日志

---

## 监控中心

支持：

- Agent Metrics
- RAG Metrics
- LLM Metrics
- Run Log
- Error Trace
- Analysis Detail
- Audit Log

用于观察工作流执行情况、模型调用情况以及系统运行状态。

---

# 技术栈

## 前端

- Streamlit

## 后端

- FastAPI

## 工作流编排

- LangGraph

## 大模型接入

- OpenAI Compatible API

## 数据存储

- SQLite
- JSON Vector Store

## 文档解析

- PDF
- DOCX


## 容器化

- Docker
- Docker Compose

---

# 系统架构

```text
┌─────────────────────────────┐
│        Streamlit UI         │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│        Service Layer        │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│       LangGraph Layer       │
└─────────────┬───────────────┘
              │
      ┌───────┼────────┐
      ▼       ▼        ▼

 Resume   Matching   Manager
 Agent     Agent      Agent

      └───────┬────────┘
              ▼

┌─────────────────────────────┐
│          RAG Layer          │
└─────────────┬───────────────┘
              ▼

┌─────────────────────────────┐
│      Repository Layer       │
└─────────────┬───────────────┘
              ▼

┌─────────────────────────────┐
│ SQLite / Vector Store / FS  │
└─────────────────────────────┘
```

详细设计说明请参考：

```text
docs/ARCHITECTURE.md
```

---

# 项目结构

```text
AI-Recruitment-Agent/

├── agents/                    # Agent 实现
├── api/                       # FastAPI 接口层
├── app/                       # 应用启动与配置
│
├── data/
│   ├── knowledge_base/        # 知识库源文件
│   ├── uploads/               # 上传文件
│   └── vector_store/          # 本地向量库
│
├── db/                        # SQLite 数据库
├── docs/                      # 项目文档
├── exports/                   # 导出报告
│
├── frontend/                  # Streamlit 前端
├── graph/                     # LangGraph 工作流
├── llm/                       # LLM 适配层
├── memory/                    # 历史记录与状态管理
├── monitoring/                # 监控与可观测性
├── prompts/                   # Prompt 模板
├── rag/                       # RAG 检索系统
├── repositories/              # Repository 层
├── services/                  # 业务服务层
├── tests/                     # 测试代码
├── tools/                     # 工具模块
├── utils/                     # 通用工具
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── streamlit_app.py
└── README.md
```

---

# 快速开始

## 1. 克隆项目

```bash
git clone <repository-url>
cd AI-Recruitment-Agent
```

---

## 2. 创建虚拟环境

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

Linux / macOS：

```bash
source .venv/bin/activate
```

---

## 3. 安装依赖

```bash
pip install -r requirements.txt
```

---

## 4. 配置环境变量

复制：

```text
.env.example
```

创建：

```text
.env
```

示例：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url
MODEL_NAME=your_model
```

根据实际模型服务商调整配置。

---

## 5. 启动 Streamlit

```bash
streamlit run streamlit_app.py
```

或：

```bash
start_streamlit.bat
```

---

## 6. 启动 FastAPI

```bash
start_fastapi.bat
```

---

## 7. Docker 部署

```bash
docker-compose up -d
```

---

# 知识库导入

知识库目录：

```text
data/knowledge_base/
```

导入后写入：

```text
data/vector_store/shared_knowledge.json
```

系统支持重复执行导入操作。

知识块使用稳定 Chunk ID 去重：

```text
source
chunk_position
normalized_text
```

生成：

```text
chunk_id
```

因此重复导入不会产生重复向量记录。

---

# 监控中心

监控中心提供：

### Agent Metrics

记录：

- 节点执行次数
- 平均耗时
- 成功率

---

### RAG Metrics

记录：

- retrieval_count
- retrieval_hit_count
- retrieval_miss_count
- average_retrieval_time

---

### LLM Metrics

记录：

- llm_calls
- llm_failures
- average_response_time
- fallback_calls

---

### Run Log

记录工作流执行过程。

---

### Error Trace

记录异常与失败调用。

---

### Audit Log

记录关键业务操作。

---

# 文档

项目文档位于：

```text
docs/
```

推荐阅读顺序：

```text
README.md
    ↓
docs/ARCHITECTURE.md
    ↓
docs/OPERATIONS.md
    ↓
docs/DEVELOPMENT_LOG.md
```

---

# 开发说明

项目开发过程中使用了 AI 工具辅助：

- ChatGPT
- OpenAI Codex

主要用于：

- 架构讨论
- 方案验证
- Bug 排查辅助
- 文档生成辅助

最终实现、功能验证、问题定位与工程决策均经过人工确认。

---

# 现存问题

- 可能存在的bug若干
- 部分文件代码行数过多，未能及时解耦，可维护性偏低


# License

根据项目实际情况补充。


