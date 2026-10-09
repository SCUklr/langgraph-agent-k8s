# LangGraph Agent 服务镜像
FROM python:3.12-slim

# 不生成 .pyc、日志直接输出（容器里必须）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 单独 copy requirements 并安装，这样改代码时这层缓存仍然有效
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 只复制运行必需的代码
COPY llm.py tools.py agent.py server.py ./

# 非 root 用户运行（K8s 安全基线要求）
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

ENV CHECKPOINT_DB=/data/checkpoints.sqlite

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
