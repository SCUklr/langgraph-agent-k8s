#!/usr/bin/env bash
# 一键：构建镜像 -> 载入 minikube -> 建 Secret -> 部署 -> 等待就绪
#
# 用法（必须在**新开的终端**里跑，才能读到 ~/.zshrc 里的环境变量）：
#     cd ~/langgraph-starter && ./deploy.sh
#
# 必需环境变量：DEEPSEEK_API_KEY
# 可选环境变量：DEEPSEEK_BASE_URL、TAVILY_API_KEY（联网搜索用，不配则搜索工具降级）
set -euo pipefail

# 镜像 tag 用版本号递增，不要复用同一个 tag。
# 原因：同名 tag + imagePullPolicy: IfNotPresent 时，K8s 和节点运行时都可能继续用旧镜像
#（实测踩过：minikube image load 不会覆盖已存在的同名 tag，Pod 一直在跑旧代码）。
# 生产环境通用做法是用不可变 tag：git SHA 或构建流水线号。
IMAGE="langgraph-agent:1.2"
NS="ai-agent"
DEPLOY="langgraph-agent"

echo "==> 0/5 前置检查"
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker 引擎没启动。先执行：orb start" >&2
    exit 1
fi
if ! minikube status >/dev/null 2>&1; then
    echo "❌ minikube 没启动。先执行：minikube start --driver=docker" >&2
    exit 1
fi
: "${DEEPSEEK_API_KEY:?❌ 缺 DEEPSEEK_API_KEY，请在新终端里运行本脚本}"

echo "==> 1/5 构建镜像 $IMAGE"
docker build -t "$IMAGE" .

echo "==> 2/5 把镜像载入 minikube 节点"
minikube image load "$IMAGE"

echo "==> 3/5 创建 Namespace 与 Secret"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
# 清理历史遗留的旧 Secret 名
kubectl -n "$NS" delete secret deepseek --ignore-not-found >/dev/null 2>&1 || true
# Secret 从当前 shell 环境变量读取，不落盘、不进镜像
kubectl -n "$NS" create secret generic agent-secrets \
    --from-literal=DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" \
    --from-literal=DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}" \
    --from-literal=TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
    --dry-run=client -o yaml | kubectl apply -f -

echo "==> 4/5 应用部署清单"
kubectl apply -f k8s/app.yaml

# 保险起见再触发一次滚动重启：
#   正常情况换了新 tag，pod 模板变了，K8s 会自动滚动更新。
#   但本地开发时如果忘了改 tag，这行能保证 Pod 用上新镜像。
echo "==> 4.5/5 触发滚动重启（确保 Pod 用上新镜像）"
kubectl -n "$NS" rollout restart deployment/"$DEPLOY"

echo "==> 5/5 等待滚动更新完成"
kubectl -n "$NS" rollout status deployment/"$DEPLOY" --timeout=180s

echo
kubectl -n "$NS" get pods -o wide
kubectl -n "$NS" get svc,pvc
echo
echo "✅ 部署完成。本地访问方式："
echo "   kubectl -n $NS port-forward svc/$DEPLOY 8080:80"
echo "   然后另开终端：curl -X POST http://127.0.0.1:8080/chat \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"message\":\"北京天气怎么样\",\"thread_id\":\"t1\"}'"
