# 样例：一个进行到一半的真实任务

> 用途：**few-shot 夹具**。协议文字读十遍，不如看一份跑起来的现场。
> 读顺序：`plan.md` → `steps/02-design/step.md` → `decisions.md` → `state.json`

## 现场说明

任务「把周报生成流程自动化」进行到第 6 轮：

- `01-scope` 已冻结（done）
- `02-design` 进行中（execute），本轮在等用户确认是否支持历史回填
- `03-build` 未开工（draft）

## 关键看点

| 看什么 | 在哪 |
|---|---|
| 步骤总表怎么定义验收要点 | `.spec-pact/plan.md` §三 |
| 分文档头部五个字段（含 `upstream_check`） | `steps/02-design/step.md` 开头 |
| 决策为什么要写「为什么」 | `decisions.md` 的 D-01 / D-02 |
| 改动只记 diff、不写理由 | `changes.md` |
| 外部引用不落副本、只登记 | `refs.md`（r01 / r02 均为绝对路径） |
| 三向一致长什么样 | `plan.md` 状态列 ＝ `step.md` 的 `status` ＝ `state.json` 的 `phase` |

## 自己验一遍

```bash
python scripts/sp.py sync   --root examples/sample-change   # 三向一致
python scripts/sp.py status --root examples/sample-change -v
python scripts/sp.py lint   --root examples/sample-change -v
```

把 `steps/02-design/step.md` 的 `status` 改成 `done` 再跑 `sync`，会看到它如何抓出不一致 —— 这就是三向校验存在的理由。
