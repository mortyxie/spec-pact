# 路径与命名规范

> 在 **新建文件 / 目录前**、**命名有争议时**、**`sp.py lint` 报错时**按需加载。
> 核心分工：**工程代码用蛇形，项目之外的文档用连字符** —— 用命名风格本身区分"这是什么"。

## 一、分区（顶层固定，不随意新增）

| 目录 | 用途 | 谁写 |
|---|---|---|
| `resource/` | 本地素材、用户提供的原始资料 | 人 / AI 只读消费 |
| `work/` | 中间结果、草稿、临时产物 | AI，可随时清理 |
| `output/` | 交付物，版本化只增不覆盖 | AI |
| `log/` | 运行与审计日志 | 只由 `sp.py` 写 |
| `.spec-pact/` | 协议内核（plan / steps / decisions / changes / refs / state / env） | 以脚本写为主，state.json 禁止手改 |

- 新增顶层目录 = 结构变更，须先 `sp.py decision` 记录理由。
- 点开头的目录（`.spec-pact` `.git`）豁免命名校验。

## 二、风格分派（按类型，不按心情）

| 类型 | 风格 | 正则 |
|---|---|---|
| **文档**（`.md` `.txt` `.rst`） | kebab-case | `^[a-z0-9]+(-[a-z0-9]+)*\.[a-z0-9]+$` |
| **代码 / 配置**（`.py` `.js` `.ts` `.json` `.yaml` …） | snake_case | `^[a-z0-9]+(_[a-z0-9]+)*\.[a-z0-9]+$` |
| **目录** | kebab-case | `^[a-z0-9]+(-[a-z0-9]+)*$` |
| **代码区目录**（`src/` `lib/` `tests/` `app/` `packages/` 之下） | snake_case | `^[a-z0-9]+(_[a-z0-9]+)*$` |

示例：`v2-plan.md` ✅ ｜ `my_notes.md` ❌ ｜ `my_module.py` ✅ ｜ `my-module.py` ❌ ｜ `01-scope/` ✅ ｜ `src/my_pkg/` ✅

> 这条分派的用处：看到 `a-b-c.md` 就知道是文档，看到 `a_b_c.py` 就知道是工程代码，不必打开文件。

## 三、标识性名称豁免

以下**不受工作区命名规则约束**，遵循 GitHub / 生态惯例：

- skill 名与仓库名（`spec-pact`）、分支 / tag / release 名
- 生态约定文件：`README.md` `LICENSE` `SKILL.md` `Makefile` `package.json` `skill_meta.json`（登记在 `config.naming.whitelist`）

## 四、编号与时间戳

- **步骤目录**：`steps/NN-slug/`，NN 两位数字从 `01` 起（`01-scope`、`02-design`）。数字前缀保证文件管理器里的顺序稳定，不依赖 state.json 排序。
- **交付物版本**：`output/<name>-v01.<ext>`，两位数，只增不覆盖。
- **快照**：`.spec-pact/snapshots/s01-20261028-2100.<ext>`。
- **文件名内时间戳**：`YYYYMMDD-HHMM`（文件名里不能有冒号）。
- **文档正文内时间**：`YYYY-MM-DD HH:mm`。

## 五、层级与禁用名

- 目录深度 ≤ 3 层（`resource/` `work/` `output/` `log/` 之下再分两层为限）；`.spec-pact/steps/` 子树豁免。
- 禁用：`temp` `tmp` `新建文件夹` `未命名` `副本` `最终版` `final2` `test1` `a.md` 等临时 / 含糊 / 单字母名。
- 禁止出现：空格、中文、大写字母、括号、`&`、`+`、连续点、首尾分隔符。

## 六、存量文件的处理

| 情况 | 策略 |
|---|---|
| 用户已有的非规范文件 | **不强改、不阻断**。`lint` 归入 `soft` 列表提示 |
| AI 新建文件 | **必须合规**。`sp.py touch` 前置拦截，不合规直接 exit 2 |
| 代码项目想整体收紧 | `config.naming.strict_existing: true`，存量也计入 `HARD` |

> 分工原则：**新建靠 `touch` 阻断，存量靠 `lint` 提示**。永远不要为了"规范"去批量重命名用户的老文件 —— 那会打断外部引用。

## 七、机器校验

```bash
python scripts/sp.py touch output/report_v1.md --kind output   # 新建前：命名/分区/越界/深度 四查
python scripts/sp.py lint -v                                   # 全树扫描
```

`lint` 输出两类：

- `HARD`：结构问题（超深、越界），**阻断**（exit 2）
- `soft`：非规范命名。非 strict 模式下**容忍**，只提示

## 八、越界规则（与命名同级重要）

- 一切写入必须在 root 内。`touch` 用 `Path.resolve()` 判定，`../` 逃逸直接拒绝。
- 外部资料**不复制进 root**，登记进 `.spec-pact/refs.md`（绝对路径 + 用途 + 校验值），只读访问。
- 唯一允许写到 root 之外的位置：用户级 `~/.spec-pact/env.json`（跨项目依赖登记表）。
