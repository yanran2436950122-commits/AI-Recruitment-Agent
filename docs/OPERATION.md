# 运维与故障排查手册

本文档用于说明系统运行过程中常见问题的排查与处理方式。

适用于：

- 本地开发环境
- 测试环境
- 单机部署环境

详细设计请参考：

```text
docs/ARCHITECTURE.md
```

---

# 1. 环境检查

启动项目前建议确认：

## Python 版本

建议：

```text
Python 3.11+
```

检查：

```bash
python --version
```

---

## 依赖安装

安装：

```bash
pip install -r requirements.txt
```

检查：

```bash
pip list
```

---

## 环境变量

确认：

```text
.env
```

存在。

至少包含：

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
MODEL_NAME=
```

---

## 数据目录

确认以下目录存在：

```text
data/
data/uploads/
data/knowledge_base/
data/vector_store/
db/
exports/
```

---

# 2. 系统无法启动

## 现象

启动时报：

```text
ImportError
ModuleNotFoundError
```

---

## 排查步骤

检查虚拟环境：

```bash
where python
```

或：

```bash
which python
```

确认使用的是项目虚拟环境。

---

检查依赖：

```bash
pip show streamlit
pip show fastapi
```

---

检查 requirements：

```bash
pip install -r requirements.txt
```

重新安装。

---

## 处理方案

删除虚拟环境后重新创建：

```bash
python -m venv .venv
```

重新安装依赖。

---

# 3. Streamlit 页面异常

## 现象

页面显示：

```text
NameError
AttributeError
ImportError
```

---

## 排查步骤

查看完整 Traceback。

定位：

```text
文件路径
行号
函数名称
```

例如：

```text
frontend/legacy.py
line 1024
```

---

检查：

- 方法是否存在
- import 是否正确
- 是否存在循环引用

---

## 处理方案

优先修复：

```text
ImportError
AttributeError
```

再处理业务逻辑问题。

---

# 4. 页面切换响应较慢

## 现象

切换页面时等待时间明显。

---

## 原因

Streamlit 页面切换会触发：

```text
Script Rerun
```

部分初始化逻辑会重复执行。

---

## 排查步骤

检查：

```python
initialize_xxx()
load_xxx()
restore_xxx()
```

是否在每次页面切换时执行。

---

检查：

```python
@st.cache_data
@st.cache_resource
```

是否合理使用。

---

## 处理方案

避免：

```python
页面切换时重新初始化服务
页面切换时重复读取数据库
页面切换时重复加载知识库
```

---

# 5. 知识库导入问题

## 现象

导入失败。

---

## 排查步骤

检查：

```text
data/knowledge_base/
```

是否存在文件。

---

确认支持格式：

```text
txt
md
pdf
docx
```

---

查看导入结果：

```text
files
chunks
inserted
skipped
```

---

## 处理方案

重新放置知识库文件。

重新执行导入。

---

# 6. 知识库重复导入

## 现象

多次导入相同知识库。

---

## 正常结果

第一次：

```text
inserted > 0
skipped = 0
```

第二次：

```text
inserted = 0
skipped > 0
```

---

## 异常结果

第二次导入后：

```text
inserted > 0
```

仍持续增长。

---

## 排查步骤

检查：

```text
rag/vector_store.py
```

确认：

```python
chunk_id
```

去重逻辑存在。

---

检查：

```text
data/vector_store/shared_knowledge.json
```

文档数量。

---

## 处理方案

重新构建向量库。

必要时清空：

```text
shared_knowledge.json
```

后重新导入。

---

# 7. RAG 未返回上下文

## 现象

页面显示：

```text
知识库暂无命中内容
```

---

## 排查步骤

检查：

```text
data/vector_store/shared_knowledge.json
```

是否为空。

---

检查：

```text
retrieved_count
```

是否为：

```text
0
```

---

检查查询内容：

- 是否过短
- 是否缺少关键词

---

## 处理方案

重新导入知识库。

使用更明确的问题测试。

---

# 8. 简历上传失败

## 现象

上传后无法解析。

---

## 支持格式

```text
pdf
docx
```

---

## 排查步骤

确认：

- 文件未损坏
- 文件大小正常
- 文件内容可打开

---

检查：

```text
data/uploads/
```

是否生成文件。

---

## 处理方案

重新上传。

优先使用：

```text
PDF
DOCX
```

---
# 另：docx文件的部分内容无法解析，容易产生错误，建议使用pdf
---
---
# 9. 历史记录缺失

## 现象

分析完成后未出现在历史记录中。

---

## 排查步骤

检查：

```text
analysis_id
```

是否生成。

---

检查数据库：

```text
db/
```

确认记录已写入。

---

## 处理方案

重新执行分析。

查看：

```text
Run Log
Error Trace
```

是否存在异常。

---

# 10. PDF 导出失败

## 现象

点击导出时报错。

---

## 排查步骤

检查：

```text
exports/
```

目录权限。

---

检查：

```text
analysis_result
```

是否为空。

---

检查：

```bash
pip show reportlab
```

是否安装。

---

## 处理方案

安装：

```bash
pip install reportlab
```

重新启动系统。

---

# 11. 监控中心无数据

## 现象

显示：

```text
暂无 Run Log
暂无 Error Trace
```

---

## 说明

首次启动且未执行分析时属于正常情况。

---

## 排查步骤

执行一次完整分析流程。

再次查看监控中心。

---

# 12. Audit Log 字段为空

## 现象

以下字段为空：

```text
analysis_id
company_id
job_id
```

---

## 说明

并非所有操作都关联这些对象。

例如：

Candidate 操作通常不包含：

```text
company_id
```

---

HR 操作通常包含：

```text
company_id
job_id
```

---

非分析类操作可能不包含：

```text
analysis_id
```

---

字段为空不一定表示异常。

应结合：

```text
action
actor_type
```

共同判断。

---

# 13. 数据恢复

## 上传文件

目录：

```text
data/uploads/
```

---

## 知识库

目录：

```text
data/knowledge_base/
```

---

## 向量库

目录：

```text
data/vector_store/
```

---

## 数据库

目录：

```text
db/
```

---

建议定期备份：

```text
db/
data/vector_store/
```

即可恢复绝大部分业务数据。

---

# 14. 获取更多诊断信息

优先查看：

```text
监控中心
```

包括：

```text
Run Log
Error Trace
Agent Metrics
RAG Metrics
LLM Metrics
Audit Log
```

其次查看：

```text
控制台日志
Streamlit 输出
FastAPI 输出
```

最后再定位具体模块。

---

# 15. 问题反馈建议

提交问题时建议同时提供：

- 错误截图
- 完整 Traceback
- 操作步骤
- 运行环境
- Python 版本
- 项目版本

便于快速定位问题。