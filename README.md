# LangChain + LangGraph 本地开发起步模板（DeepSeek 版）

本机已配好的一套可运行环境，用来学习和开发 LangChain / LangGraph。

---

## 一、环境信息

| 项 | 值 |
|---|---|
| 虚拟环境 | `/Users/konglingran030521/venvs/agent` （Python 3.12.13，uv 创建） |
| 项目目录 | `/Users/konglingran030521/langgraph-starter` |
| 模型 | DeepSeek（`deepseek-chat`），凭证来自 `~/.zshrc` |

已安装的关键包：

```
langchain              1.4.3      langgraph              1.2.14
langchain-core         1.6.7      langgraph-checkpoint-sqlite  3.1.1
langchain-deepseek     1.1.1      langgraph-cli          0.4.33
langchain-openai       1.6.7      langchain-mcp-adapters 0.3.2
langchain-chroma       1.1.0      chromadb               1.5.9
fastapi                0.142.4    uvicorn                0.54.0
mcp                    1.30.0     opentelemetry-api      1.42.1（锁死，见下）
```

> 环境是隔离的，不会影响你机器上原有的 miniconda / Homebrew Python 环境。

### ⚠️ 一个必须知道的版本约束

`opentelemetry-api` **必须锁在 1.42.1**。若被升级到 1.45+，`chromadb` 会直接崩溃：

```
ImportError: cannot import name '_ExtendedAttributes' from 'opentelemetry.util.types'
```

原因是 `opentelemetry-sdk` 1.42.1 依赖 api 中的 `_ExtendedAttributes`，而该符号在 1.45 被移除。
`pyproject.toml` 里已经写死 `opentelemetry-api==1.42.1`。

**如果哪天 chromadb 又报这个错**，执行：
```bash
uv pip install --python ~/venvs/agent/bin/python "opentelemetry-api==1.42.1"
```


---

## 二、快速开始

### 方式 1：跑 LangChain 基础示例

```bash
cd ~/langgraph-starter
~/venvs/agent/bin/python demo_langchain.py
```

演示三件事：直接调用模型 → LCEL 链（`prompt | llm | parser`）→ 绑定工具。

### 方式 2：跑 LangGraph Agent（含多轮记忆）

```bash
cd ~/langgraph-starter
~/venvs/agent/bin/python demo_langgraph.py
```

会真实调用 DeepSeek，让模型自己决定是否调工具，并把对话状态写进 `checkpoints.sqlite`。
再跑一次，模型能记得上一轮说过什么。想重置就 `rm checkpoints.sqlite`。

### 方式 3：打开 LangGraph Studio（可视化调试）

```bash
cd ~/langgraph-starter
~/venvs/agent/bin/langgraph dev
```

然后浏览器打开 **http://127.0.0.1:2024** —— 这就是 Studio，能看到图结构、逐节点执行、查看每步状态。

> 必须在**新开的终端**里运行，否则读不到 `~/.zshrc` 里的 `DEEPSEEK_API_KEY`。

---

## 三、目录结构

```
langgraph-starter/
├── llm.py                # 模型工厂：环境变量 -> LangChain 模型对象
├── tools.py              # 工具集：@tool 装饰的函数
├── agent.py              # LangGraph 图（Studio 入口：agent 变量）
├── demo_langchain.py     # 示例 1：LangChain 基础
├── demo_langgraph.py     # 示例 2：LangGraph + SQLite 持久化
├── langgraph.json        # Studio / Server 的配置
├── pyproject.toml        # 依赖声明
├── .env                  # 本地环境变量（默认留空，走 shell）
└── .env.example          # 换机器时复制改这个
```

---

## 四、核心概念（读代码前先看这里）

### LangChain 到底是什么

它不启动服务、没有配置文件，就是一堆 Python 库。分三类包，**按需装**：

| 类别 | 包 | 作用 |
|---|---|---|
| 核心抽象 | `langchain-core` | 自动被装，别手动装 |
| 高层 API | `langchain` | agent、tool、chain |
| 模型适配器 | `langchain-deepseek` / `-openai` / `-anthropic` … | 每个厂商一个包 |
| 向量库适配器 | `langchain-chroma` / `-qdrant` … | 每个库一个包 |

**千万别 `pip install langchain[all]`** —— 会拖几百个包互相打架。

### LangGraph 在解决什么问题

普通 LangChain 链是**直线**执行：A → B → C。

真实 Agent 需要**循环**：模型说"我要调工具" → 执行工具 → 结果喂回模型 → 模型再决定……

LangGraph 用「图」描述这种流程：

```
START → model ──(有 tool_calls)──→ tools
          │                          │
          └──(没有)──→ END            └──→ 回到 model
```

`agent.py` 里的 `build_graph()` 就是这个结构，对应关系：

| 代码 | 含义 |
|---|---|
| `StateGraph(AgentState)` | 定义一张图，状态是一个消息列表 |
| `add_node("model", ...)` | 加一个节点（一个处理步骤） |
| `add_conditional_edges("model", tools_condition)` | 加条件分支：要不要调工具 |
| `add_edge("tools", "model")` | 工具执行完回到模型 —— **这个回边就是"循环"** |
| `compile(checkpointer=...)` | 编译成可执行对象；传 checkpointer 才有持久化 |

### checkpointer 为什么重要

不挂 checkpointer 的图是**无状态**的：每次 `invoke` 都从头开始，聊完就忘。

挂上 `SqliteSaver` 之后，LangGraph 会把每一步状态写进 SQLite，于是你免费获得：

- 多轮对话记忆（靠 `thread_id` 区分不同会话）
- 断点续跑
- 人工介入（human-in-the-loop）

`demo_langgraph.py` 里第二次用**全新的 checkpointer 实例**读出了 12 条历史消息，就是在验证这件事。

---

## 五、换成别的模型

只改 `llm.py` 的 `get_llm()` 一个函数，其他代码不用动。

比如换成 OpenAI：

```python
from langchain_openai import ChatOpenAI

return ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
```

换成任意 OpenAI 兼容服务（通义千问、Kimi、本地 vLLM 等），只要它提供 `/v1` 端点：

```python
return ChatOpenAI(
    model="qwen-plus",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)
```

---

## 六、常见问题

**Q：`ModuleNotFoundError: No module named 'langchain'`**
用错解释器了。必须用 `~/venvs/agent/bin/python`，或者在 VS Code 里把解释器切到 `/Users/konglingran030521/venvs/agent/bin/python`。

**Q：`缺少 DEEPSEEK_API_KEY`**
在 IDE 里跑时读不到 `~/.zshrc`。把 `.env.example` 复制成 `.env` 填上值即可。

**Q：`langgraph dev` 报 `No dependencies found in config`**
`langgraph.json` 的 `dependencies` 不能是空数组，且项目要有 `pyproject.toml`。本模板已配好。

**Q：想清空对话历史**
`rm checkpoints.sqlite`。

**Q：这个环境会不会影响我其他项目？**
不会。它是独立虚拟环境，只在显式调用 `~/venvs/agent/bin/python` 时生效。

---

## 七、部署到 Kubernetes（云原生链路）

这一节演示「**写 AI 应用 → 容器化 → 部署到 K8s 算力平台**」的完整链路。

### 前置：启动本地集群

```bash
orb start                                              # 启动容器引擎
minikube start --driver=docker --cpus=2 --memory=3072  # 起单节点 K8s
```

### 一键部署

```bash
cd ~/langgraph-starter
./deploy.sh
```

脚本做的事：构建镜像 → `minikube image load` 载入节点 → 从环境变量创建 Secret → `kubectl apply` → 等待 rollout。

> 必须在**新开的终端**里跑，否则读不到 `~/.zshrc` 里的 `DEEPSEEK_API_KEY`。

### 访问服务

```bash
kubectl -n ai-agent port-forward svc/langgraph-agent 8080:80
```

另开终端：

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
curl -X POST http://127.0.0.1:8080/chat \
     -H 'Content-Type: application/json' \
     -d '{"message":"北京天气怎么样","thread_id":"t1"}'
curl http://127.0.0.1:8080/history/t1
```

### 部署清单讲了什么（`k8s/app.yaml`）

| 资源 | 作用 | 面试考点 |
|---|---|---|
| **Namespace** | 环境隔离 `ai-agent` | 多租户 |
| **Secret** | 存 API Key，不写进镜像 | 配置与代码分离 |
| **PVC** | 1Gi 持久卷挂到 `/data` | 有状态服务、存储类 |
| **Deployment** | 声明式副本数管理 | 滚动更新、自愈 |
| **Service** | ClusterIP 稳定虚拟 IP | 服务发现、负载均衡 |

另外几个刻意设计的点：

- `envFrom.secretRef` —— API Key 从 Secret 注入，镜像里没有明文
- `resources.requests/limits` —— 不声明配额会被调度器当成"无底线"，云计算里的基本要求
- `livenessProbe` vs `readinessProbe` —— 前者失败**重启**容器，后者失败只**摘流量**，语义完全不同
- `imagePullPolicy: IfNotPresent` —— 配合 `minikube image load`，不去远程仓库拉
- Dockerfile 用**非 root 用户**跑（`uid 10001`）—— 容器安全基线

### 你可以在面试里演示的四个现象

```bash
# 1. 滚动更新（改代码后重新部署，服务不中断）
kubectl -n ai-agent rollout restart deployment/langgraph-agent

# 2. 自愈：删掉 Pod，Deployment 会自动重建
kubectl -n ai-agent delete pod <pod-name>
kubectl -n ai-agent get pods -w

# 3. 持久化：换 Pod 之后，对话历史依然在（因为存在 PVC 里）
curl http://127.0.0.1:8080/history/t1

# 4. 水平扩展
kubectl -n ai-agent scale deployment/langgraph-agent --replicas=3
```

### 排查命令

```bash
kubectl -n ai-agent get all
kubectl -n ai-agent describe pod <pod-name>     # 看事件，排查调度/拉镜像失败
kubectl -n ai-agent logs -f deploy/langgraph-agent
kubectl -n ai-agent exec -it <pod-name> -- sh   # 进容器
k9s -n ai-agent                                  # 终端 UI，比敲命令直观
stern -n ai-agent langgraph                      # 多 Pod 日志聚合
```

### 清理

```bash
kubectl delete namespace ai-agent   # 删除全部资源（含 PVC）
minikube stop                       # 停集群
```

