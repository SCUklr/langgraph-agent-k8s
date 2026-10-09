# LangChain + LangGraph 本地开发起步模板（DeepSeek 版）

本机已配好的一套可运行环境，用来学习和开发 LangChain / LangGraph。

---

## 一、环境信息

| 项 | 值 |
|---|---|
| 虚拟环境 | `/Users/konglingran030521/venvs/agent` （Python 3.12.13，uv 创建） |
| 项目目录 | `/Users/konglingran030521/langgraph-starter` |
| 模型 | DeepSeek（`deepseek-chat`），凭证来自 `~/.zshrc` |
| 工具 | `get_weather`（模拟）、`add`（本地）、`web_search`（Tavily 真实联网） |

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

### ⭐ 工具 = Agent 的能力边界

**这是理解 Agent 最重要的一条**：模型自己只能靠**训练数据里的静态知识**回答。
想要实时信息，**必须有人把对应工具交到它手上**。没注册的能力，它完全做不到。

`tools.py` 里注册了 3 个工具：

| 工具 | 类型 | 说明 |
|---|---|---|
| `get_weather` | 模拟 | 返回内置的假数据，用于演示"工具调用"机制本身 |
| `add` | 本地计算 | 演示最简单的纯函数工具 |
| **`web_search`** | **真实联网** | 走 Tavily API，能查实时信息 |

**模型怎么决定用不用工具？** 看 docstring。给它一个真实问题的实测结果：

| 问题 | 模型判断 | 结果 |
|---|---|---|
| "有馬かな是谁？" | 我训练数据里有 ✅ | **直接回答**（2 条消息，不走 tools） |
| "最近有什么 AI 大新闻？" | 实时信息，我不知道 ❌ | **调用 2 次 `web_search`**（5 条消息） |

> 在 LangGraph Studio 里能**亲眼看到**这个分叉：前者只有 `model` 亮，后者 `model → tools → model` 依次亮起。

### ⏰ 一个必须知道的坑：大模型没有时钟

模型**不知道今天几号**。如果不告诉它，它只能瞎猜——或者去搜"今天的日期"，
结果拿到一堆年份互相矛盾的网页（我们实测踩过这个坑）。

`agent.py` 里的 `_system_prompt()` 解决这件事：每次调用模型前，
把当前时间动态注入 system 消息。**这是生产级 Agent 的标准做法。**

```
当前时间：2026-10-09 22:05（星期五，CST）。
```

> 为什么不用工具而用 system prompt？因为时间几乎每轮对话都要用到，
> 走工具要多绕一圈（模型决策 → 工具调用 → 结果回喂），白白浪费一次 LLM 调用。

### 🔁 另一个坑：外部 API 必须重试

`web_search` 调的是境外 API。实测中遇到过：

```
ConnectError: SSL: UNEXPECTED_EOF_WHILE_READING
```

**排查过程**（值得记下来）：

1. 连续压测发现成功率约 87%，**不是硬性阻断**
2. 但延迟分两档：**1.1 秒** 和 **11 秒** —— 这个跳跃说明代理在超时后切换节点
3. `dig` 发现域名解析到 `198.18.0.234` —— 保留测试网段，是**代理软件 fake-ip 模式**的指纹
4. 路由表确认 `198.18.0.0/15 → utun5`，即走了 TUN 虚拟网卡

**结论**：不是代码问题，是代理链路不稳定。

**修复**：`tools.py` 里给外部调用加了**指数退避重试**（3 次，0.8s / 2s）：

```python
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.8, 2.0)
```

两个设计要点：

| 要点 | 原因 |
|---|---|
| **只重试网络层错误**（`httpx.TransportError`）和 5xx | 4xx 是请求本身的问题（Key 无效、配额用尽），重试没有意义，只会浪费配额 |
| **把重试次数告诉模型** | 工具返回里带上"第 N 次尝试才成功"，模型可以如实告知用户网络有波动 |

> **通用原则**：任何跨网络的外部调用都必须有重试。
> 单次失败率 1% 听起来很低，但一个 Agent 一轮对话可能调 3~5 次外部 API，
> 累积失败率就变成 5%~15% —— 用户会经常看到报错。

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

