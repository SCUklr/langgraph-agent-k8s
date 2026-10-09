"""工具集：@tool 装饰器把普通 Python 函数变成模型能调用的工具。

要点：
  · 函数签名 = 模型的入参 schema（类型注解必须有）
  · docstring = 模型判断「什么时候用这个工具」的唯一依据，要写清楚
"""

from __future__ import annotations

from langchain_core.tools import tool

_FAKE_WEATHER = {
    "北京": "晴，12~24°C，西北风 3 级",
    "上海": "多云，16~25°C，东南风 2 级",
    "深圳": "雷阵雨，24~31°C，南风 4 级",
    "成都": "阴，14~21°C，微风",
}


@tool
def get_weather(city: str) -> str:
    """查询指定城市的当前天气。输入城市中文名，如「北京」。"""
    return _FAKE_WEATHER.get(city, f"{city}：晴，15~26°C（模拟数据）")


@tool
def add(a: int, b: int) -> int:
    """计算两个整数之和。"""
    return a + b


TOOLS = [get_weather, add]
