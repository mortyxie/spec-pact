---
name: spec-pact
description: "多轮项目协作协议：任务拆成带验收标准的步骤，进度与关键决策由 Python 状态机 scripts/sp.py 保管；每轮回复顶部输出「步骤 / 阶段 / 轮次 / 风险」状态头，强制单根收口、外部只读、命名规范、主文档与分步文档三向一致。用户说 spec-pact，或进入多轮项目实施时启用。"
license: MIT
metadata:
  version: "2.1.1"
---

# spec-pact

**规范驱动的协作契约。** spec 借自 OpenSpec（规范持久化 / 结构化变更 / 归档审计）；pact 是 Plan·Align·Correct·Terminate 四阶段，也是"契约"本身。

与 v1 的根本差别：**状态不靠记忆，靠 `scripts/sp.py`。**

## 一、入口与开场

**入口一律走启动器**（它自己不需要 python 就能跑；找不到就 `exit 6`，绝不自动下载）：

| 平台 | 命令 |
|---|---|
| macOS / Linux / Git Bash | `sh scripts/sp.sh <命令>` |
| Windows cmd / PowerShell | `scripts\sp.cmd <命令>` |

开场三件事：

1. `sp.sh doctor` —— 自检；未初始化则 `sp.sh init --task "<任务名>"`（**init 自带解释器体检**）
2. `sp.sh env` —— 解释器分级 + 依赖复用登记（换 agent 只重跑这一步）
3. `sp.sh tick --did 0` —— 取状态头

## 二、每轮铁律

**生成回复之前**调一次，把输出贴回复顶部：

```
sh scripts/sp.sh tick --did <上一轮动作> --summary "<一句话>"
```

| `--did` | 含义 |
|---|---|
| `+1` | 推进：产出新内容 / 通过一项验收 |
| `0` | 维持：澄清、只读探查 |
| `-1` | 回退：推翻已锁定决策 / 重做 / 撤销写入 |
| `wait` | 等用户输入（不计入停滞） |

- 状态头形如 `▸ spec-pact · 步骤 01-scope (1/5) · execute · 轮 3/12 · 上轮 +1 · 风险 无`
- **退出码 4**（stalled / overrun / backtrack-review）→ 必须停下处理，不得继续推进
- **退出码 6**（无可用 python）→ 按 `protocol/bootstrap.md` 走三条出路，**不得私自下载 python**

## 三、步骤模型

| 层级 | 位置 |
|---|---|
| 任务（主文档） | `.spec-pact/plan.md` 的「步骤总表」 |
| 步骤（分文档） | `.spec-pact/steps/NN-slug/step.md` |

- 步骤状态：`draft → execute → verify → done`（可插 `blocked`）
- **三向一致**：plan.md 表格状态 ＝ step.md 的 `status` ＝ state.json 的 `phase`，`sp.py sync` 机械校验
- 初始化时把步骤与每步**验收标准**定好并让用户确认；之后增删改步骤 = **计划变更**：`sp.py decision` + `plan_version+1` + 同步主文档
- 验收标准优先写**可机械验证**项（文件存在 / 正则命中 / 命令退出码 / 行数阈值）

## 四、决策 vs 改动

**三问，任一"是"就是决策**：① 会牵动其他步骤或文件吗 ② 撤回来代价大、后续都基于它吗 ③ 推翻了已锁定的东西吗

| 类型 | 命令 | 落盘 | 内容 |
|---|---|---|---|
| 决策 | `sp.py decision --trigger ① --text "..."` | `decisions.md`，即时 | 结论 + **为什么** + 触发器 + 轮次 |
| 改动 | `sp.py change --text "..."` | `changes.md`，可攒批 | 只记 diff 摘要 |

- 软信号（用户强调 / 反复纠结）→ **打断问一句**"这算决策吗"，不擅自定性
- 判定模糊时问，不猜。漏记决策的代价远大于多记一条

## 五、路径与边界

| 目录 | 用途 |
|---|---|
| `resource/` | 本地素材，只读消费 |
| `work/` | 中间结果、草稿，可清理 |
| `output/` | 交付物，版本化只增 |
| `log/` | 运行与审计日志，脚本写 |
| `.spec-pact/` | plan · steps · decisions · changes · refs · state · env |

- **单根收口**：一切写入在 root 内。**外部资料不复制**，登记进 `.spec-pact/refs.md`，只读访问
- 唯一例外：用户级 `~/.spec-pact/env.json`（跨项目依赖登记表）
- 新建文件 / 目录前先 `sp.py touch <path> --kind work|resource|output`（校验命名 / 分区 / 越界 / 深度）
- 命名：**文档 kebab-case、代码 snake_case、目录 kebab-case**（详见 `protocol/naming.md`）

## 六、收尾

| 时机 | 动作 |
|---|---|
| 步骤进 verify | `sp.sh sync` + `sp.sh lint` |
| 手工改过主文档索引 | `sp.sh sync --ack`（清 pending_sync 提醒） |
| 步骤完成 | `sp.sh step <id> --phase done` → `sp.sh archive <id>`（**就地冻结，不改路径**） |
| 交接 | `sp.sh handoff`（自包含包到 `output/handoff_<ts>/`） |

## 七、边界（明确不属于本 skill）

- 文档排版规范 → 可选适配器 `targets/local-md.md`，项目明确绑定后才生效
- 具体 CLI 命令模板（编辑器 / 网盘 / 在线文档）→ 归对应工具自己的 skill
- 业务环境检测（某工具装没装、网络通不通）→ 不做
- **要不要装 python**：本 skill 只做检测 / 分级 / 复用登记，装与不装由用户决定（`protocol/bootstrap.md`）

## 八、参考文件（按需加载）

| 文件 | 内容 | 何时读 |
|---|---|---|
| `protocol/bootstrap.md` | 启动器阶梯、无 python 三条出路、依赖复用、手动模式 | 首次安装 / 换机器 / 换 agent / exit 6 |
| `protocol/state-machine.md` | 阶段、tick 语义、watchdog 阈值、退出码、交接 | 初始化 / 风险触发 / 交接 |
| `protocol/doc-tree.md` | 主分文档骨架、三向一致、向上校验、归档 | 建或改步骤文档 |
| `protocol/naming.md` | 分区、风格分派、时间戳、深度、lint 行为 | 新建文件 / 命名争议 |
| `protocol/decision-capture.md` | 判定三问、触发器、软信号 | 判断是否记录时 |
| `targets/local-md.md` | 可选：本地 md 文档排版约定 | 项目绑定该适配器时 |
| `examples/sample-change/` | 一个完整任务的真实文件样例 | 首次使用 / 执行偏差时 |
