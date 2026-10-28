# spec-pact · 规范驱动的协作契约

> 让多轮项目不跑偏：任务拆成带验收标准的步骤，进度由 Python 状态机保管，每轮开头告诉你"在哪、还有多少风险"。

## 名字由来

| 词 | 来源 | 含义 |
|---|---|---|
| **spec** | 借自 [OpenSpec](https://openspec.dev) | specification，规范。规范驱动开发：先把"要做什么"写成持久化文档，再动手。v1 的 `changes/` + `archive/` 骨架即照搬它 |
| **PACT** | 四阶段首字母 | **P**lan / **A**lign / **C**orrect / **T**erminate |
| | 英文原义 | pact = 契约、约定 |

合起来：**先就 spec（做什么）达成 pact（契约），再动手。**

## 解决什么问题

- 长对话里 **AI 丢失当前状态**：在做什么、锁定了什么、还差什么
- 不确定时**靠猜**，事后大面积返工
- 关键决策只在对话里说过，换个上下文就没了
- 多轮迭代后**主文档与分文档互相矛盾**，没人发现
- 中途交接时上下文传不完整

## 与 v1 的根本差别

| | v1.1 | v2.0 |
|---|---|---|
| 状态靠什么 | LLM 记忆 + 手改 `state.json` | **`scripts/sp.py` 唯一权威** |
| 每轮输出 | 7 行状态栏，模型自己构造 | **1 行状态头，脚本生成** |
| 任务粒度 | 一份 `proposal.md` | **主文档 + 步骤分文档 + 三向校验** |
| 决策分级 | L1 / L2 / L3 | **决策 / 改动** 两级 |
| 风险控制 | 无 | **watchdog**（停滞 / 超轮 / 回退） |
| 外部产物 | POPO 硬编码在主链路 | **可选适配器 `targets/`** |
| 归档 | 整个目录 `mv`（引用悬挂） | **就地冻结，路径不变** |

## 快速开始

入口是**启动器**，不是裸 python——它自己不需要 python 就能运行，找不到 python 会 `exit 6` 并给出三条出路，**绝不自动下载**（`protocol/bootstrap.md`）：

| 平台 | 入口 |
|---|---|
| macOS / Linux / Git Bash | `sh scripts/sp.sh ...` |
| Windows cmd / PowerShell | `scripts\sp.cmd ...` |

```bash
# 1. 初始化（在你的项目根目录；init 自带解释器体检）
sh scripts/sp.sh init --task "任务名"

# 2. 写 plan.md 的步骤总表，然后导入
sh scripts/sp.sh plan --import

# 3. 每轮开头（唯一强制调用）
sh scripts/sp.sh tick --did "+1" --summary "本轮做了什么"
```

`tick` 输出贴到回复顶部：

```
▸ spec-pact · 步骤 02-design (2/3) · execute · 轮 2/12 · 上轮 +1 · 风险 无
```

## 工作区长什么样

```
<root>/
├── .spec-pact/          plan.md · steps/ · decisions.md · changes.md · refs.md · state.json · env.json
├── resource/            本地素材（只读）
├── work/                中间结果、草稿
├── output/              交付物，版本化只增
└── log/                 运行与审计日志
```

外部资料**不复制进 root**，只登记到 `.spec-pact/refs.md` 并只读访问。

## 命令速查

| 命令 | 作用 |
|---|---|
| `init --task <名>` | 建骨架、初始 state |
| `doctor` | 自检（文件完整、python、可写、漏调检测） |
| `env` | 解释器分级 + 依赖复用登记（换 agent 只跑这个） |
| `plan --import` | 解析 plan.md 步骤总表，建步骤目录 |
| `tick --did <+1\|0\|-1\|wait>` | 每轮唯一调用，出状态头 |
| `status [-v]` | 查看状态（不推进轮次） |
| `step <id> --phase <p>` | 改步骤阶段 |
| `decision --trigger ① --text "..."` | 记决策（含为什么） |
| `change --text "..."` | 记改动（只记 diff） |
| `accept <id> [--item N]` | 查 / 勾验收项 |
| `sync` | 三向一致性校验 |
| `lint [-v]` | 命名 / 越界 / 深度扫描 |
| `touch <path> --kind <区>` | 新建文件前的路径闸门 |
| `archive <id>` | 就地冻结步骤 |
| `handoff` | 打自包含交接包 |

## 什么不属于它

- **文档排版规范** → 可选适配器 `targets/local-md.md`，项目声明 `target: local-md` 才生效
- **具体 CLI 命令模板**（在线文档 / 网盘 / 编辑器） → 归对应工具自己的 skill
- **业务环境检测**（某工具装没装、网络通不通） → 不做，只做 `sp.py doctor` 自检
- **装不装 python** → 只检测 / 分级 / 登记复用，装与不装由用户决定

## 文件结构

```
spec-pact/
├── SKILL.md                    ← 内核，常驻加载
├── README.md                   ← 本文件：定位 / 名字 / 边界
├── scripts/
│   ├── sp.sh                   ← 入口（sh，PATH 坏了也能跑）
│   ├── sp.cmd                  ← 入口（Windows cmd/PowerShell）
│   └── sp.py                   ← 状态机，零第三方依赖
├── protocol/
│   ├── bootstrap.md            启动器阶梯、无 python 出路、依赖复用
│   ├── state-machine.md        阶段、tick、watchdog、交接
│   ├── doc-tree.md             主分文档、三向一致、向上校验
│   ├── naming.md               分区、风格分派、越界
│   └── decision-capture.md     决策判定三问、触发器
├── targets/local-md.md         可选：本地 md 排版
└── examples/sample-change/     一个跑到一半的真实任务
```

## 版本记录

- **2.1.0（2026-10-28）** 补齐启动地：新增 `scripts/sp.sh` / `sp.cmd` 零依赖启动器（PATH 坏掉也能跑出结论），解释器按 A-system → B-agent-managed → C-sandbox 阶梯探测，无可用 python 时 `exit 6` 并给三条出路，绝不自动下载；`init` 内置解释器体检并写出 `env.json`；依赖统一登记到用户级 registry。见 `protocol/bootstrap.md`。
- **2.0.0（2026-10-28）** 重写。状态机从"文字约定"变成可执行程序；任务模型从单层 proposal 变成主文档 + 步骤分文档 + 三向校验；决策分级简化为两级；新增 watchdog 与运行环境契约；移除 POPO 硬耦合；归档改就地冻结。
- **1.1.0（2026-08-10）** 修复快照路径双定义、diff 计数无持久化字段、Terminate 后 active 悬空。
- **1.0.x** PACT + OpenSpec 融合初版。
