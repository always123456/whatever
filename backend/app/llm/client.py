"""OpenAI 兼容 chat client（DeepSeek），httpx 直连，无 openai 库依赖。

- api_key 获取顺序：settings.llm_api_key → 环境变量 DEEPSEEK_API_KEY → Windows 注册表兜底
- 无 key / 网络失败 / 超时 / 解析失败 → 抛 LLMUnavailable，由调用方走确定性降级
"""
import json
import os

import httpx

from ..config import settings


class LLMUnavailable(Exception):
    """LLM 不可用（无 key / 网络失败 / 超时），调用方应走确定性降级。"""


def api_key() -> str:
    if settings.llm_api_key:
        return settings.llm_api_key
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    # Windows 注册表兜底（本机开发环境，key 存于 HKCU\Environment）
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _ = winreg.QueryValueEx(k, "DEEPSEEK_API_KEY")
            return val or ""
    except Exception:
        return ""
    return ""


def chat_json(messages: list[dict], temperature: float = 0.0) -> dict:
    """调用 chat completions，要求 JSON 输出，返回解析后的 dict。失败抛 LLMUnavailable。"""
    key = api_key()
    if not key:
        raise LLMUnavailable("no api key")
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = httpx.post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=settings.llm_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:  # noqa: BLE001  网络/解析失败一律降级
        raise LLMUnavailable(str(e)) from e
