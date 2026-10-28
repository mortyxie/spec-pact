# bootstrap · 启动地与运行环境契约

> 这一份回答两个问题：**在什么都没有的机器上，spec-pact 怎么启动**；**多开几个 agent，怎么不把 python 和依赖装十遍**。

## 一、鸡生蛋问题

入口原来是 `python scripts/sp.py init`——但"要跑 python 才能检查 python 在不在"是死循环。所以真正的入口是两个**不含 python 也能运行**的启动器：

| 平台 | 入口 |
|---|---|
| macOS / Linux / Git Bash | `sh scripts/sp.sh <命令>` |
| Windows cmd / PowerShell | `scripts\sp.cmd <命令>` |

启动器只用 shell 内建命令（`case` / `cd` / `pwd` / `printf`），**PATH 坏掉也能跑出结论**。它只做一件事：找一个 ≥3.8 的 python，然后把参数原样交给 `sp.py`，并把 `sp.py` 的退出码原样返回。

```bash
sh scripts/sp.sh init --task "季度复盘"     # 等价于 python scripts/sp.py init --task ...
sh scripts/sp.sh tick --did +1
```

已装好 python、想直接敲 `python scripts/sp.py` 也可以——**`init` 自己会做解释器体检**（见第四节），不需要额外记得跑 `env`。

## 二、解释器阶梯

按顺序探测，**命中即用，绝不下载**：

| 序 | 来源 | 分级 | 说明 |
|---|---|---|---|
| 1 | `$SP_PYTHON` | — | 用户显式指定，最高优先级；不可用则警告并继续下探 |
| 2 | `py -3`（Windows） | A | py launcher 解析出真实解释器路径后再判定分级 |
| 3 | PATH 上的 `python3` / `python`（**跳过 agent 托管目录**） | A / B | 命中 agent 目录时记下但不立即用 |
| 4 | 常见安装目录 | A | `/usr/bin` `/usr/local/bin` `/opt/homebrew/bin`；`C:\Python3*` `%ProgramFiles%\Python3*` `%LOCALAPPDATA%\Programs\Python\Python3*` |
| 5 | PATH 上被跳过的 agent 解释器 | B | 复用已有的一份 |
| 6 | `~/.workbuddy` `~/.local/share/uv` `~/.pyenv` 下的运行时 | B | 同上，只复用 |

分级语义：

| 分级 | 判定 | 用法 |
|---|---|---|
| **A-system** | 系统安装（含**不在 PATH** 的 `C:\Python315`、`/usr/bin/python3`、Homebrew、conda） | 首选。`sp.py` 跑在它上面最稳 |
| **B-agent-managed** | `~/.workbuddy` `~/.cursor` `~/.claude` `~/.codex` `pyenv` `uv` `pipx` `npm` `WindowsApps` | **允许复用，禁止重下** |
| **C-sandbox** | `/tmp`、`%TEMP%`、`sandbox` 等临时路径 | **禁止装依赖**，会话结束即失效 |

**为什么第 4 步在"PATH python"之后还要再探一遍目录**：很多机器装了 python 却没进 PATH（本机就是 `C:\Python315` 不在 PATH），agent 看不到就以为"没有 python"，于是又下一份——这是"每开一个对话下载一遍 python"的主要成因之一。

> `SP_PACT_PROBE_DIRS=/opt/py:/data/py` 可**替代**默认的第 4 步探测，用于非标准安装位置。

## 三、没有 python 时：exit 6

六个来源全落空，启动器**不装任何东西**，打印三条出路并 `exit 6`：

1. **装一份**（一次性）：`winget install -e --id Python.Python.3.12` / `brew install python@3.12` / `sudo apt install python3`
2. **已有但不在 PATH**：`SP_PYTHON=/abs/path/to/python sh scripts/sp.sh <命令>`
3. **装不了 / 不想装**：进入**手动模式**（下节）

装完之后把路径登记到用户级 registry，后续项目直接命中，不再重复找：

```bash
sh scripts/sp.sh env --dep pyyaml --register /usr/lib/python3/dist-packages --version 6.0
```

## 四、init 内置体检

`sp.py init` 不再只是建目录，它**顺带完成解释器体检**并写出 `.spec-pact/env.json`：

```
ok init · root=/work/quarterly · task=季度复盘
  python 3.13.14 [B-agent-managed] C:\Users\...\.workbuddy\binaries\python\versions\3.13.12\python.exe
  ! 改用系统解释器：SP_PYTHON=C:\Python315\python.exe（或直接 C:\Python315\python.exe scripts/sp.py …）；不要为此下载新 python
  env → .spec-pact/env.json · 候选 3 · registry deps=1
```

`sp.py doctor` 每次会话首次运行，也会补检这个字段（`env.json` 缺失则自动重建），并对非 A-system 解释器给 `warn`——**warn 不阻断**，因为 B 级也可以用。

## 五、依赖治理

| 规则 | 含义 |
|---|---|
| `sp.py` 零第三方依赖 | **不得为运行它安装任何东西**（仅 stdlib，3.8+） |
| 用户级 registry | `~/.spec-pact/env.json` 是**唯一允许写到 root 之外**的位置，存"哪个包在哪" |
| 先查后装 | 装之前 `sp.py env --dep <name>`：`reuse` 就直接用，`missing` 才装，装完 `--register` |
| 禁止每会话新建 venv | 已有环境能用就用；确实需要隔离时一个项目一个 venv，且登记 |
| 禁止重复 `pip install` | 命中 registry 即复用它记录的路径 |

## 六、换 agent 的接口

协议本体跟具体 agent 解耦，只靠两个接缝：

1. **启动器**——不认 agent，只认"能不能跑 python"
2. **`sp.py env`**——把当前 agent 的解释器写入 `.spec-pact/env.json`

换到别的 agent（Cursor / Claude Code / 别的 IDE）时只需重跑一次 `env`，其余文件、状态、步骤全部照旧。

## 七、手动模式（degraded）

真的没有 python、也装不了时，协议**不假装还能机检**：

- 状态头仍按标签行格式，但首行标 degraded，且**必须写明「未经机器校验」**：

```
▸ spec-pact[degraded] · <任务名> · 进度 ?/? 步完成 · 未经机器校验

步骤：02-design 方案设计 (?)
阶段：execute
轮次：?/?
上轮：?
验收：?
风险：未知（degraded）
```
- 第一条要在 `decisions.md` 记：`D-000 进入手动模式，原因 <...>`，并写明恢复条件
- `state.json` 允许人工编辑，但**不得声称经过 `sync` 校验**；跨步骤推进前必须人工核对 plan.md / step.md 两处
- 手动模式只应作为过渡，超过 2 个步骤没恢复 → 停下来向用户报告，不要硬撑

## 八、自检清单

```bash
sh scripts/sp.sh doctor          # python 版本 / 分级 / 目录 / state / 距上次 tick
sh scripts/sp.sh env             # 候选解释器 + 推荐 + registry
sh scripts/sp.sh status -v       # 当前步骤与风险
```

- [ ] `doctor` 无 `missing`、无 `fail`
- [ ] `env` 的 `running` 与 `recommended` 一致（不一致就按提示改 `SP_PYTHON`）
- [ ] 没为 `sp.py` 装过任何包
