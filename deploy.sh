#!/usr/bin/env bash
# 一键：构建镜像 -> 载入 minikube -> 建 Secret -> 部署 -> 等待就绪
#
# 用法（必须在**新开的终端**里跑，才能读到 ~/.zshrc 里的 DEEPSEEK_API_KEY）：
#     cd ~/langgraph-starter && ./deploy.sh
set -euo pipefail

IMAGE="langgraph-agent:1.0"
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
kubectl -n "$NS" create secret generic deepseek \
    --from-literal=DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" \
    --from-literal=DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}" \
    --dry-run=client -o yaml | kubectl apply -f -

echo "==> 4/5 应用部署清单"
kubectl apply -f k8s/app.yaml

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
