"""数据库连接辅助函数。"""

from contextlib import contextmanager
from typing import Iterator, Optional

from app.config import POSTGRES_DSN


@contextmanager
def get_postgres_connection() -> Iterator[Optional[object]]:
    """创建 PostgreSQL 连接，依赖缺失或连接失败时返回空连接。"""

    try:
        import psycopg
    except ImportError:
        yield None
        return

    connection = None
    try:
        connection = psycopg.connect(POSTGRES_DSN)
        yield connection
    except Exception:
        yield None
    finally:
        if connection is not None:
            connection.close()
