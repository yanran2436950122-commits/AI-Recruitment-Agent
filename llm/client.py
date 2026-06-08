"""OpenAI 兼容协议的大模型客户端。"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

LAST_LLM_ERROR = ""
"""最近一次大模型调用错误信息。"""


@dataclass(frozen=True)
class LLMConfig:
    """大模型连接配置。"""

    api_key: str
    base_url: str
    model: str
    timeout: float
    temperature: float


def get_llm_config() -> LLMConfig:
    """从环境变量读取大模型配置。"""

    load_env_file()
    return LLMConfig(
        api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "",
        base_url=(
            os.getenv("LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ),
        model=os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "",
        timeout=float(os.getenv("LLM_TIMEOUT", "30")),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
    )


def load_env_file() -> None:
    """读取项目根目录的 .env 文件，并写入尚未设置的环境变量。"""

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
            continue
        key, value = cleaned.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def is_llm_enabled() -> bool:
    """判断当前环境是否已经配置可用的大模型。"""

    config = get_llm_config()
    return bool(config.api_key and config.model)


def chat_completion(system_prompt: str, user_prompt: str) -> Optional[str]:
    """调用 OpenAI 兼容的聊天补全接口，失败时返回空值。"""

    global LAST_LLM_ERROR
    LAST_LLM_ERROR = ""
    start_time = time.perf_counter()
    config = get_llm_config()
    if not config.api_key or not config.model:
        LAST_LLM_ERROR = "未配置 LLM_API_KEY 或 LLM_MODEL"
        record_llm_observation(success=False, start_time=start_time, fallback=True)
        return None

    url = config.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = str(exc)
        LAST_LLM_ERROR = f"HTTP {exc.code}: {detail[:300]}"
        record_llm_observation(success=False, start_time=start_time, fallback=True)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        LAST_LLM_ERROR = str(exc)
        record_llm_observation(success=False, start_time=start_time, fallback=True)
        return None

    choices = data.get("choices") or []
    if not choices:
        LAST_LLM_ERROR = "接口返回中没有 choices"
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        LAST_LLM_ERROR = "接口返回中没有 message.content"
        record_llm_observation(success=False, start_time=start_time, fallback=True)
        return None
    record_llm_observation(success=True, start_time=start_time, fallback=False)
    return str(content).strip() if content else None


def record_llm_observation(success: bool, start_time: float, fallback: bool) -> None:
    """记录 LLM 调用观测指标，监控模块不可用时静默降级。"""

    try:
        from monitoring.monitor_service import get_monitor_service

        get_monitor_service().record_llm_metric(
            success=success,
            response_time_ms=(time.perf_counter() - start_time) * 1000,
            fallback=fallback,
        )
    except Exception:
        return


def get_last_llm_error() -> str:
    """读取最近一次大模型调用错误信息。"""

    return LAST_LLM_ERROR


def parse_json_object(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """从大模型输出中提取 JSON 对象。"""

    if not text:
        return None
    cleaned = text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.S)
    if fenced_match:
        cleaned = fenced_match.group(1)
    else:
        object_match = re.search(r"\{.*\}", cleaned, re.S)
        if object_match:
            cleaned = object_match.group(0)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def normalize_string_list(value: Any) -> List[str]:
    """将大模型返回的列表字段规范化为字符串列表。"""

    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]
