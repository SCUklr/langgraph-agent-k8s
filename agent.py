"""LangGraph Agent：手写「模型 ⇄ 工具」循环图。

这个图就是 Agent 的本质：
    START -> model ──(需要调工具)──> tools -> model -> ... -> END
                 └──(不需要)──────────────────────────────> END

langgraph.json 通过 ./agent.py:agent 引用下面这个编译好的图，
所以 `langgraph dev` 能在 Studio 里把它画出来。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from llm import get_llm
from tools import TOOLS

_WEEKDAYS = "一二三四五六日"


class AgentState(TypedDict):
    """图的状态：整个图只共享一个对话消息列表。

    Annotated[..., add_messages] 的含义是「新消息追加，而不是覆盖」。
    """

    messages: Annotated[list[AnyMessage], add_messages]


def _system_prompt() -> str:
    """每次调用模型前动态生成系统提示。

    关键点：**大模型没有时钟，也不知道今天几号**。不告诉它，它就只能瞎猜，
    或者去搜"今天日期"——而搜索结果往往给出互相矛盾的年份。
    所以这里把当前时间注入进去。这是生产级 Agent 的标准做法。
    """
    now = datetime.now().astimezone()
    date_line = (
        f"当前时间：{now.strftime('%Y-%m-%d %H:%M')}"
        f"（星期{_WEEKDAYS[now.weekday()]}，{now.strftime('%Z')}）。"
    )
    base = os.getenv(
        "AGENT_SYSTEM_PROMPT",
        "你是一个乐于助人的中文 AI 助手，可以查询天气、做算术、联网搜索。",
    )
    return (
        f"{base}\n\n{date_line}\n"
        "当问题涉及「最新」「最近」「今天」「现在」等实时信息时，"
        "优先调用 web_search 工具核实，不要凭记忆猜测。\n"
        "如果工具返回了信息，必须基于工具返回的内容回答，并说明来源。"
    )


def build_graph(checkpointer=None):
    """构建并编译图。

    Args:
        checkpointer: 传入 SqliteSaver / PostgresSaver 等即可获得持久化
            （多轮记忆、断点续跑、human-in-the-loop 都依赖它）。
            传 None 则图是无状态的。
    """
    model = get_llm().bind_tools(TOOLS)

    def call_model(state: AgentState):
        # 每次都在历史前插入一条最新的 system 消息（含当前时间）。
        # 它不写回 state，所以不会在历史里堆积。
        messages = [SystemMessage(content=_system_prompt()), *state["messages"]]
        return {"messages": [model.invoke(messages)]}

    builder = StateGraph(AgentState)
    builder.add_node("model", call_model)
    builder.add_node("tools", ToolNode(TOOLS))

    builder.add_edge(START, "model")
    # tools_condition 是官方预置的判定函数：模型返回 tool_calls 就走 "tools"，
    # 否则走 "__end__" 直接结束。
    builder.add_conditional_edges("model", tools_condition)
    builder.add_edge("tools", "model")

    return builder.compile(checkpointer=checkpointer)


# ---- langgraph dev / Studio 的入口对象 ----
# 注意：Studio 自己负责持久化，所以这里不挂 checkpointer。
agent = build_graph()
