"""FastAPI 服务层：把 LangGraph Agent 暴露成 HTTP 接口，供 Kubernetes 部署。

本地运行：
    ~/venvs/agent/bin/python -m uvicorn server:app --reload

容器运行：
    docker run -p 8000:8000 -e DEEPSEEK_API_KEY=your-api-key langgraph-agent:1.0

接口：
    GET  /health            健康检查（K8s livenessProbe 用）
    GET  /ready             就绪检查（K8s readinessProbe 用）
    POST /chat              对话，带会话记忆
    GET  /history/{thread}  查看某会话的完整历史
"""

from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field

from agent import build_graph

CHECKPOINT_DB = os.getenv("CHECKPOINT_DB", "checkpoints.sqlite")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入")
    thread_id: str = Field("default", description="会话 ID，不同 ID 之间上下文隔离")


class ChatResponse(BaseModel):
    thread_id: str
    reply: str
    message_count: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时构建图并挂载 SQLite 持久化；关闭时释放连接。"""
    os.makedirs(os.path.dirname(CHECKPOINT_DB) or ".", exist_ok=True)
    # check_same_thread=False：FastAPI 的同步端点跑在线程池里
    conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    app.state.conn = conn
    app.state.graph = build_graph(checkpointer=SqliteSaver(conn))
    print(f"[startup] checkpoint db = {CHECKPOINT_DB}", file=sys.stderr)
    try:
        yield
    finally:
        conn.close()


app = FastAPI(
    title="LangGraph Agent",
    description="LangGraph Agent 部署在 Kubernetes 上的示例服务",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    """存活探针：进程还在就直接返回 ok。"""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, Any]:
    """就绪探针：确认图已经构建完成，可以接流量。"""
    return {
        "ready": getattr(app.state, "graph", None) is not None,
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "checkpoint_db": CHECKPOINT_DB,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """一轮对话。同一个 thread_id 会自动带上历史上下文。"""
    graph = getattr(app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="图尚未就绪")

    cfg = {"configurable": {"thread_id": req.thread_id}}
    state = graph.invoke({"messages": [("user", req.message)]}, cfg)
    messages = state["messages"]
    return ChatResponse(
        thread_id=req.thread_id,
        reply=messages[-1].content,
        message_count=len(messages),
    )


@app.get("/history/{thread_id}")
def history(thread_id: str) -> dict[str, Any]:
    """读取某个会话被持久化的完整消息历史。"""
    graph = getattr(app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="图尚未就绪")

    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    messages = snapshot.values.get("messages", [])
    return {
        "thread_id": thread_id,
        "count": len(messages),
        "messages": [{"role": m.type, "content": m.content} for m in messages],
    }
