"""LangGraph Agent：手写「模型 ⇄ 工具」循环图。

这个图就是 Agent 的本质：
    START -> model ──(需要调工具)──> tools -> model -> ... -> END
                 └──(不需要)──────────────────────────────> END

langgraph.json 通过 ./agent.py:agent 引用下面这个编译好的图，
所以 `langgraph dev` 能在 Studio 里把它画出来。
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from llm import get_llm
from tools import TOOLS


class AgentState(TypedDict):
    """图的状态：整个图只共享一个对话消息列表。

    Annotated[..., add_messages] 的含义是「新消息追加，而不是覆盖」。
    """

    messages: Annotated[list[AnyMessage], add_messages]


def build_graph(checkpointer=None):
    """构建并编译图。

    Args:
        checkpointer: 传入 SqliteSaver / PostgresSaver 等即可获得持久化
            （多轮记忆、断点续跑、human-in-the-loop 都依赖它）。
            传 None 则图是无状态的。
    """
    model = get_llm().bind_tools(TOOLS)

    def call_model(state: AgentState):
        # 把整个历史丢给模型，模型自己决定「直接回答」还是「要求调工具」
        return {"messages": [model.invoke(state["messages"])]}

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
