"""LangChain 基础用法演示 —— 不涉及 LangGraph。

运行：
    ~/venvs/agent/bin/python demo_langchain.py
"""

from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from llm import get_llm
from tools import TOOLS


def main() -> None:
    llm = get_llm()

    print("[1] 直接调用模型")
    print("   ", llm.invoke("用一句话解释什么是 LangChain").content)

    print("\n[2] LCEL 链：prompt | llm | parser")
    chain = (
        ChatPromptTemplate.from_template("把下面这句话翻译成英文，只输出译文：{text}")
        | llm
        | StrOutputParser()
    )
    print("   ", chain.invoke({"text": "今天北京的天气不错"}))

    print("\n[3] 绑定工具（真正的工具调用循环在 demo_langgraph.py）")
    bound = llm.bind_tools(TOOLS)
    reply = bound.invoke("北京天气怎么样？")
    calls = getattr(reply, "tool_calls", None) or []
    print("    模型决定调用的工具:", [c["name"] for c in calls] or "（无）")


if __name__ == "__main__":
    main()
