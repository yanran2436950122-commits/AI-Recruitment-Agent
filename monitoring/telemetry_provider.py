"""可观测性 TelemetryProvider 抽象接口。"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class TelemetryProvider(ABC):
    """定义运行日志、节点日志、错误追踪和指标记录的统一接口。"""

    @abstractmethod
    def record_run(self, run: Dict[str, Any]) -> None:
        """记录或更新一次工作流运行。"""

    @abstractmethod
    def record_node(self, node: Dict[str, Any]) -> None:
        """记录一次 Agent 节点执行。"""

    @abstractmethod
    def record_error(self, error: Dict[str, Any]) -> None:
        """记录一次异常追踪。"""

    @abstractmethod
    def record_metric(self, metric: Dict[str, Any]) -> None:
        """记录一个通用指标点。"""

    @abstractmethod
    def fetch_rows(self, table_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """读取指定表的最近记录。"""
