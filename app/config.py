"""应用配置、外部服务连接信息与文件系统路径。"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
"""项目根目录。"""

DATA_DIR = BASE_DIR / "data"
"""用于保存上传简历和本地知识库文件的目录。"""

UPLOAD_DIR = DATA_DIR / "uploads"
"""上传文件生命周期管理根目录。"""

KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
"""存放 PDF/DOCX/TXT 面试题知识文件的目录。"""

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
"""本地解析器支持的简历和知识库文件类型。"""

KNOWLEDGE_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
"""知识库导入流程支持的文件类型。"""

MATCH_PASS_SCORE = 70.0
"""跳过优化并生成面试题所需的最低匹配分。"""

MAX_RETRY_COUNT = 3
"""进入最终报告前允许的最大优化与重新匹配次数。"""

MEMORY_DIR = DATA_DIR / "memory"
"""本地降级记忆数据目录。"""

VECTOR_STORE_DIR = DATA_DIR / "vector_store"
"""本地降级向量库数据目录。"""

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
"""Redis 会话记忆连接地址。"""

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://postgres:postgres@localhost:5432/ai_recruitment",
)
"""PostgreSQL 长期记忆连接地址。"""

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
"""Chroma 服务主机。"""

CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
"""Chroma 服务端口。"""

VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "local")
"""向量库后端类型，支持 local、chroma，后续可扩展 milvus。"""

DISPLAY_TIMEZONE = os.getenv("DISPLAY_TIMEZONE", "Asia/Shanghai")
"""前端展示时间使用的时区，数据库和日志存储仍保持 UTC。"""
