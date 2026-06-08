# 默认招聘知识库

## AI Agent 面试题

1. 请说明 Agent 的规划、工具调用、记忆和反馈闭环如何设计。
2. 如何避免 Agent 在多轮执行中出现状态污染或无限循环？
3. 如果工具调用失败，你会如何设计降级和重试策略？

## LangGraph 面试题

1. 为什么选择 LangGraph，而不是普通链式调用？
2. AgentState 中哪些字段应该属于短期状态，哪些应该持久化？
3. 条件路由如何避免死循环？

## RAG 面试题

1. RAG 的召回、重排和生成分别解决什么问题？
2. 如何排查向量库无命中？
3. metadata filter 错误会造成什么后果？

## 向量数据库面试题

1. Chroma 和 Milvus 在本地开发和生产环境中的取舍是什么？
2. 为什么多租户检索必须依赖 scope、company_id、candidate_id、job_id？
3. 如何设计 Shared Knowledge 与 Private Memory 的隔离？

## 简历优化建议样例

- 项目经历应包含业务背景、技术方案、个人职责和可量化结果。
- 如果 JD 要求 RAG，应补充检索、Embedding、向量库、重排和评估指标。
- 如果 JD 要求 LangGraph，应说明节点设计、状态传递、条件路由和异常处理。
