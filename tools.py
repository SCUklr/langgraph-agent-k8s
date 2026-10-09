"""工具集：@tool 装饰器把普通 Python 函数变成模型能调用的工具。

三个要点：
  · 函数签名 = 模型的入参 schema（类型注解必须有）
  · docstring = 模型判断「什么时候用这个工具」的唯一依据，必须写清楚
  · **Agent 的能力边界 = 这里注册了哪些工具**。没注册的能力，模型完全做不到

最后一个尤其重要：模型本身只能靠训练数据里的静态知识回答，
想要实时信息（天气、新闻、股价）就必须有人把对应工具交到它手上。
"""

from __future__ import annotations

import os
import time

import httpx
from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# 模拟工具（不联网，返回内置数据，用于演示"工具调用"机制本身）
# ---------------------------------------------------------------------------

_FAKE_WEATHER = {
    "北京": "晴，12~24°C，西北风 3 级",
    "上海": "多云，16~25°C，东南风 2 级",
    "深圳": "雷阵雨，24~31°C，南风 4 级",
    "成都": "阴，14~21°C，微风",
}


@tool
def get_weather(city: str) -> str:
    """查询指定城市的当前天气。输入城市中文名，如「北京」。

    （演示用工具：返回内置的模拟数据，非真实天气 API。）
    """
    return _FAKE_WEATHER.get(city, f"{city}：晴，15~26°C（模拟数据）")


@tool
def add(a: int, b: int) -> int:
    """计算两个整数之和。"""
    return a + b


# ---------------------------------------------------------------------------
# 真实联网搜索工具（Tavily API）
# ---------------------------------------------------------------------------

TAVILY_ENDPOINT = "https://api.tavily.com/search"

# 重试策略：外部 API 调用必须做重试。
# 实测教训：经过代理访问境外 API 时，偶发 TLS 握手中断
# （SSL: UNEXPECTED_EOF_WHILE_READING），且同一批请求延迟会在 1s 和 11s 之间跳动
# ——说明是代理节点不稳定/自动切换导致。单次请求失败率虽低，但用户会直接看到报错。
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.8, 2.0)  # 第 1 次重试等 0.8s，第 2 次等 2s


def _post_with_retry(payload: dict) -> tuple[dict, int]:
    """带指数退避的 POST。返回 (响应 JSON, 实际尝试次数)。

    只对网络层错误重试；4xx（如 Key 无效、配额用尽）属于业务错误，重试没有意义。
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = httpx.post(TAVILY_ENDPOINT, json=payload, timeout=30.0)
            resp.raise_for_status()
            return resp.json(), attempt + 1
        except httpx.HTTPStatusError as exc:
            # 5xx 是服务端临时故障，可重试；4xx 是请求本身的问题，直接抛出
            if exc.response.status_code < 500:
                raise
            last_exc = exc
        except httpx.TransportError as exc:
            # 覆盖 ConnectError / ReadTimeout / RemoteProtocolError 等网络层错误
            last_exc = exc

        if attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)])

    assert last_exc is not None
    raise last_exc


@tool
def web_search(query: str) -> str:
    """联网搜索实时信息。

    适用场景：
      · 问题涉及「最新」「最近」「今天」「现在」等实时信息
      · 涉及新闻事件、人物近况、产品版本、价格等会变化的内容
      · 你不确定、或训练数据里没有的信息

    不适用：常识、定义、历史事实、数学计算——这些用你自己的知识回答即可。

    Args:
        query: 搜索关键词，用自然语言描述要查什么，例如「有馬かな 推しの子 角色」。
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return (
            "[搜索不可用] 服务端未配置 TAVILY_API_KEY，无法联网。"
            "请基于已有知识回答，并明确告知用户这部分内容未经联网核实。"
        )

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": 5,
        "search_depth": "basic",
        "include_answer": True,
    }

    try:
        data, attempts = _post_with_retry(payload)
    except Exception as exc:  # noqa: BLE001
        # 工具必须自己消化异常：工具报错会让整个 Agent 中断，
        # 而返回一句"搜索失败"让模型继续用已有知识回答，体验好得多。
        return (
            f"[搜索失败] 已重试 {_MAX_ATTEMPTS} 次仍未成功"
            f"（{type(exc).__name__}: {exc}）。"
            "请基于已有知识回答，并明确告知用户这部分未能联网核实。"
        )

    lines: list[str] = []
    if attempts > 1:
        lines.append(f"（注：第 {attempts} 次尝试才成功，网络有波动）")
    if data.get("answer"):
        lines.append(f"搜索摘要：{data['answer']}")
    for idx, item in enumerate(data.get("results", [])[:5], 1):
        title = item.get("title", "无标题")
        url = item.get("url", "")
        snippet = (item.get("content") or "").strip().replace("\n", " ")[:400]
        lines.append(f"{idx}. {title}\n   来源：{url}\n   摘要：{snippet}")

    return "\n".join(lines) if lines else "没有找到相关结果，请基于已有知识回答。"


# ---------------------------------------------------------------------------
# 注册所有工具 —— 这个列表就是 Agent 的全部能力
# ---------------------------------------------------------------------------

TOOLS = [get_weather, add, web_search]
