"""LangGraph 演示：手写 Agent 图 + SQLite 持久化（多轮记忆）。

运行：
    ~/venvs/agent/bin/python demo_langgraph.py

两次运行之间状态会保留，因为写进了 checkpoints.sqlite。
想从头开始就删掉这个文件。
"""

from __future__ import annotations

from langgraph.checkpoint.sqlite import SqliteSaver

from agent import build_graph

DB = "checkpoints.sqlite"
THREAD = "demo-thread-1"


def main() -> None:
    print("=== 第 1 轮：带持久化的工具调用 ===")
    with SqliteSaver.from_conn_string(DB) as saver:
        graph = build_graph(checkpointer=saver)
        cfg = {"configurable": {"thread_id": THREAD}}

        questions = ["北京今天天气怎么样？", "那上海呢？", "37 加 58 等于多少？"]
        for question in questions:
            state = graph.invoke({"messages": [("user", question)]}, cfg)
            print(f"\n用户: {question}")
            print(f"助手: {state['messages'][-1].content}")

        total = len(state["messages"])
        print(f"\n[本次会话累计 {total} 条消息]")

    print("\n=== 第 2 轮：新建 checkpointer 实例，验证状态确实落盘 ===")
    with SqliteSaver.from_conn_string(DB) as saver2:
        graph2 = build_graph(checkpointer=saver2)
        snapshot = graph2.get_state({"configurable": {"thread_id": THREAD}})
        messages = snapshot.values.get("messages", [])
        print(f"  从 {DB} 恢复出 {len(messages)} 条消息 ✅")
        if messages:
            print(f"  最后一条: {messages[-1].content[:70]}")


if __name__ == "__main__":
    main()
