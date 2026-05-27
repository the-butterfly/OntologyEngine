# 14 — LOCOMO-10 Benchmark: OE vs Mem0 Fair Comparison

> 在真实 LOCUMO-10 数据集上，使用统一的 LLM（sensenova/sensenova-6.7-flash-lite）对 OntologyEngine（OE）和 Mem0 进行公平对比。

## 背景

现有的 `04_locomo_eval` 使用的是人造数据（TechNova、CloudGroup 等），虽然可以验证 OE 的功能通路，但无法反映真实的长对话记忆检索场景。本案例直接采用 [Snap Research 的 LOCOMO-10 基准数据集](https://github.com/snap-research/locomo)，包含 10 组真实多轮对话（跨数月），以及按短期/中期/长期/跨对话分类的 QA 对。

## 公平对比原则

| 维度 | 控制方式 |
|------|---------|
| **数据集** | 同一套 LOCOMO-10 JSON |
| **Answerer LLM** | 同一模型 sensenova/sensenova-6.7-flash-lite |
| **Judge LLM** | 同一模型 sensenova/sensenova-6.7-flash-lite |
| **检索 cutoffs** | 同一组 top_k = [10, 20, 50, 200] |
| **Prompts** | 复用 memory-benchmarks 的 answer generation + judge prompt |
| **评分逻辑** | 同一套按 category 的 accuracy 计算 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `dataset.py` | LOCOMO-10 自动下载、解析、chunk 拆分 |
| `prompts.py` | Answer generation + Judge prompt（与 memory-benchmarks 对齐） |
| `clients.py` | `OEClient` 和 `Mem0Client`，统一 `add/search/delete_user` 接口 |
| `metrics.py` | 按 cutoff / category 的 accuracy 计算 + 对比表格生成 |
| `run_eval.py` | 主脚本：ingest → search → answer → judge → metrics |

## 环境准备

1. **安装依赖**（当前项目环境已包含）：
   ```bash
   pip install openai aiohttp aiolimiter tqdm python-dotenv
   ```

2. **启动 LLM 服务**（sensenova）：
   ```bash
   # 确保本地代理在 9528 端口提供 OpenAI 兼容接口
   # model: sensenova/sensenova-6.7-flash-lite
   ```

3. **（仅 Mem0 backend）启动 Mem0 OSS Server**：
   ```bash
   # 在 memory-benchmarks 项目目录下
   docker compose up -d
   # 默认地址 http://localhost:8888
   ```

## 运行方式

### 1. 评估 OE Backend

```bash
python -m examples.agent_memory.14_locomo_benchmark.run_eval \
    --backend oe \
    --project-name oe_sensenova \
    --answerer-model sensenova/sensenova-6.7-flash-lite \
    --judge-model sensenova/sensenova-6.7-flash-lite \
    --llm-base-url http://localhost:9528/v1 \
    --llm-api-key "" \
    --conversations 0,1,2 \
    --max-questions 5
```

### 2. 评估 Mem0 Backend

```bash
python -m examples.agent_memory.14_locomo_benchmark.run_eval \
    --backend mem0 \
    --project-name mem0_sensenova \
    --answerer-model sensenova/sensenova-6.7-flash-lite \
    --judge-model sensenova/sensenova-6.7-flash-lite \
    --llm-base-url http://localhost:9528/v1 \
    --llm-api-key "" \
    --conversations 0,1,2 \
    --max-questions 5
```

### 3. 生成对比报告

```bash
python -m examples.agent_memory.14_locomo_benchmark.run_eval \
    --compare \
    --oe-results results/locomo_oe/predicted_oe_sensenova/results.json \
    --mem0-results results/locomo_mem0/predicted_mem0_sensenova/results.json
```

输出示例：

```markdown
# LOCOMO Benchmark: OE vs Mem0 Comparison

| Cutoff | Backend | Overall Acc | short-term | medium-term | long-term | cross-dialogue |
|--------|---------|-------------|------------|-------------|-----------|----------------|
| top_10 | OE      | 35.0%       | 40.0%      | 30.0%       | 25.0%     | 45.0%          |
| top_10 | Mem0    | 55.0%       | 60.0%      | 50.0%       | 45.0%     | 65.0%          |
```

## 关键参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--backend` | `oe` | `oe` 或 `mem0` |
| `--conversations` | `0,1,2,3,4,5,6,7,8,9` | 评估哪些对话（LOCOMO 共 10 组） |
| `--categories` | `1,2,3,4` | 1=short-term, 2=medium-term, 3=long-term, 4=cross-dialogue |
| `--top-k-cutoffs` | `10,20,50,200` | 分别用前 N 条检索结果生成答案并评判 |
| `--predict-only` | False | 只跑 ingest+search，跳过 answer+judge（用于纯检索分析） |
| `--with-evidence` | False | 将 ground-truth evidence 传入 judge prompt |
| `--max-questions` | None | 每轮对话最多评估 N 个问题（快速测试用） |

## 与现有案例的关系

- `04_locomo_eval`：功能验证（人造数据，验证 OE 记忆管线通路）
- `14_locomo_benchmark`：**真实基准评估**（LOCOMO-10 数据集，与 Mem0 公平对比）

建议维护节奏：
1. 代码变更后先跑 `04_locomo_eval` 确保功能未损坏
2. 重大版本发布前跑 `14_locomo_benchmark` 获取与 Mem0 的量化对比
