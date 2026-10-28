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

每轮由 `tick` 生成，**原样贴到回复顶部**，不得改写格式。两列表格，四行，全部用自然语言：

```
▸ spec-pact · <任务名> · 2/9 步完成

| 项 | 内容 |
|---|---|
| 步骤 | 02-skeleton「骨架与状态机接入」（第 2 步 / 共 9 步，已完成） |
| 上一轮做完的事 | 搭骨架：SKILL.md + 转发入口 + 元数据 |
| 下一轮要做的事 | 进入 03-refs「参考文件登记与只读闸门」：外部 PDF 只登记、不复制 |
| 风险点 | 无 |
```

| 行 | 取自哪里 | 写法 |
|---|---|---|
| 步骤 | `active_step` + `steps[].title` + 序号 + 阶段 | 阶段译成人话：尚未开始 / 进行中 / 验收中 / 受阻 / 已完成 |
| 上一轮做完的事 | `last_round.summary` | 就是上一轮 `tick --summary` 写的那句话；没写就明说没写 |
| 下一轮要做的事 | 本步未过验收项 ／ 下一步的 `step.md` 「目标」首句，兜底用 plan.md 验收要点 | 本步没完 → 「还差 N 项，先做 X」；本步完了 → 「进入 NN「标题」：目标」；全完成 → 提示 handoff |
| 风险点 | watchdog 判定 | 译成人话，例如「连续 4 轮没有实际产出，大概率是方向或粒度不对——建议停下来换策略」；无风险写「无」 |

`-v` 在四行之后追加四行内部指标（阶段 / 轮次 / 验收 / 待同步），只给排障用。`status -v` 再附全步骤总览表。

有 pending-sync 时在表下加一行：

```
! pending-sync: plan.md §决策索引
```

**格式沿革（别再反复了）**：v1 七行表格 → v2.0 单行 `·` 分隔 → v2.2 表格 → v2.3 标签行 → **2.4 两列表格四行**。最终结论：要表格（`|---|---|`），但表里只放**四件人关心的事**，全部自然语言；`轮次 / 验收计数 / 停滞次数` 属于内部细节，挪进 `-v`。

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
