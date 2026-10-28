# 状态机

> 在 **初始化 / 风险触发 / 交接** 时按需加载。
> 唯一权威状态源是 `.spec-pact/state.json`，**只由 `sp.py` 写**。LLM 不推理状态，只读脚本输出。

## 一、两层阶段

| 层 | 阶段 | 说明 |
|---|---|---|
| **任务** | `plan → execute → review → done` | `blocked` 可插入 |
| **步骤** | `draft → execute → verify → done` | `blocked` 可插入 |

- v1 的 `Correct` 不再是阶段，降级为**事件**（`--did -1`）。阶段是"在哪"，回退是"发生了什么"，两者混在一起必然混乱。
- `review` = 任务级对齐（原 Align）：输出进度快照、批量落改动、检查一致性。

## 二、tick：每轮唯一强制调用

```bash
python scripts/sp.py tick --did <+1|0|-1|wait> --summary "<一句话>"
```

**语义**：`--did` 结算**上一轮**的动作，脚本返回**本轮**的状态头。所以一回合只需 1 次调用，不需要单独的 `status`。

| `--did` | 含义 | 对 watchdog 的影响 |
|---|---|---|
| `+1` | 推进：产出新内容 / 通过一项验收 | `no_progress` 归零 |
| `0` | 维持：澄清、只读探查 | `no_progress +1` |
| `-1` | 回退：推翻已锁决策 / 重做 / 撤销写入 | `no_progress +1`，`backtrack` 计数 +1 |
| `wait` | 等用户输入 | `no_progress` 归零（避免误报） |

**前置条件**（不满足即报错，不静默降级）

| 条件 | 不满足 |
|---|---|
| root 下存在 `.spec-pact/state.json` | exit 3 `not-initialized` → 先 `sp.py init` |
| `schema_version` 匹配 | exit 4 `schema-mismatch` |
| `--did` 取值合法 | exit 2 |
| `config.json` 存在 | 缺失则用内置默认值重建 |

## 三、状态头

每轮由 `tick` 生成，**原样贴到回复顶部**，不得改写格式。默认横表：

```
▸ spec-pact · <任务名> · 进度 1/9 步完成

| 步骤 | 阶段 | 轮次 | 上轮 | 验收 | 风险 |
|:---|:---|--:|:--|--:|:--|
| 01-scope 范围确认 (1/5) | execute | 3/12 | +1 推进 | 2/5 | 无 |
```

| 列 | 取值来源 |
|---|---|
| 步骤 | `state.active_step` + `steps[].title`（来自 plan.md 步骤总表「名称」列）+ `(当前/总数)` |
| 阶段 | `draft / execute / verify / blocked / done` |
| 轮次 | `steps[].turns` / `watchdog.max_turns_per_step` |
| 上轮 | `last_round.did` 六种之一：`+1 推进 / 0 维持 / -1 回退 / wait 等用户` |
| 验收 | `step.md` 的 checkbox 通过数 / 总数；无清单写 `-` |
| 风险 | `无`，或 watchdog 判定的五类风险之一 |

`-v` 换竖表，多三样东西：

```
▸ spec-pact · <任务名> · 进度 1/9 步完成

| 项 | 值 |
|:---|:---|
| 步骤 | 01-scope 范围确认 (1/5) |
| 阶段 | execute |
| 轮次 | 3/12（余 9） |
| 上轮 | +1 推进 · 写完命名规范 |
| 验收 | 2/5 · 未过 3 项 |
| 风险 | 无 |
| 待同步 | plan.md §决策索引 |
```

`status -v` 在竖表之后再附一张全步骤总览（阶段 / 轮次 / 停滞 / 验收 / 是否冻结）。

有风险时表下追加一行建议：

```
! stalled: 连续 3 轮无 +1，建议：中断当前方案 / 换策略 / 拆小步骤
```

**为什么是表不是一行**：一行版本把六个字段压成 `·` 分隔的连续文本，字段值长短不一时列不对齐，扫读成本高；表格强制列对齐，一眼能看出「轮次快满了」「验收卡住」这类异常。代价约多 3 行（≈30 tokens/轮）。

## 四、watchdog

| 风险 | 触发 | 建议动作 |
|---|---|---|
| `stalled` | 连续 `stalled_turns`（默认 3）轮无 `+1` | 中断 / 换策略 / 拆小步骤 |
| `overrun` | 本步轮数 ≥ `max_turns_per_step`（默认 12） | 拆步或重估范围 |
| `backtrack` | 本轮 `-1` | 记录决策 + 评估影响面 |
| `backtrack-review` | 连续 2 次 `-1` | **强制停下对齐**，不得继续推进 |
| `drift` | `lint` 检出命名 / 越界违规 | 立即修正 |

**阈值依据（坦白说明）**：3 / 12 是经验起点，不是数据推导。

- `stalled=3`：1 轮无产出正常（读大文件、等澄清），2 轮可疑，3 轮必须干预。
- `overrun=12`：一个步骤应当能在 12 轮内闭环。超了说明**粒度错了该拆步**，而不是该硬推。

可配 `config.json → watchdog`：严格 `2 / 8`，默认 `3 / 12`，宽松 `4 / 20`。**建议先跑一个真实项目再回填**。

## 五、退出码

| 码 | 含义 | 调用方应做什么 |
|---|---|---|
| 0 | 正常 | 继续 |
| 2 | 违规（命名 / 越界 / 非法参数） | 修正后重试，不得绕过 |
| 3 | 未初始化 | 先 `sp.py init` |
| 4 | 有风险（stalled / overrun / backtrack-review） | **停下处理**，向用户报告 |
| 6 | 无可用 python（仅启动器返回） | 见 `protocol/bootstrap.md`，**不得自动下载** |

## 六、防漏调

- 每次写 `state.json` 前备份到 `log/state_<ts>.json`，滚动保留最近 5 份。
- `sp.py doctor` 检测"距上次 tick 超过 180 分钟" → 提示疑似漏调。
- `log/tick.log` 逐条记录 `n / did / step / risk / summary`，可事后复盘。

## 七、交接

```bash
python scripts/sp.py handoff      # → output/handoff_<YYYYMMDD-HHMM>/
```

包内是**自包含**的：`spec_pact/`（plan + steps + decisions + changes + refs + state）＋ `handoff.md` 五段说明（这是什么 / 做到哪了 / 接下来 / 交付清单 / 如何接收）。

**接收方**：把包放进自己 root → `sp.py doctor` → `sp.py tick --did 0`，即恢复现场。

对方只给了产物、没有 `.spec-pact/` 时 → 降级为初始化流程，主动追问：目标？边界？已做过的关键决策？
