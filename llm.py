"""模型工厂：统一从环境变量读取 DeepSeek 配置。

你的 ~/.zshrc 里已经配置好：
    export DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
    export DEEPSEEK_API_KEY=sk-***

这里只做一件事：把「环境变量」翻译成「LangChain 模型对象」。
所有 Agent 代码都通过 get_llm() 拿模型，换厂商时只改这一个文件。
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

# 读取同目录下的 .env（文件不存在时静默跳过）。
# 默认不覆盖已存在的环境变量，所以 shell 里的值优先级更高。
load_dotenv()

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"


def get_llm(temperature: float = 0.0, **kwargs) -> BaseChatModel:
    """返回一个 DeepSeek 聊天模型实例。

    优先使用官方适配器 langchain-deepseek；若未安装则回退到
    langchain-openai（DeepSeek 的 /v1 端点就是 OpenAI 协议）。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "缺少 DEEPSEEK_API_KEY。\n"
            "  · 新开一个终端（~/.zshrc 里已配置好），或\n"
            "  · 在 IDE 里运行时把 .env.example 复制为 .env 并填值"
        )

    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    base_url = os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL

    try:
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(
            model=model,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
    except ImportError:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
