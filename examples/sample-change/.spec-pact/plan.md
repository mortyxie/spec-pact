# 把周报生成流程自动化

> status: execute
> updated: 2026-10-28 21:05
> plan_version: 1
> target: local-md

## 一、任务定义

把每周手工拼装的周报，改成脚本从多个来源汇总生成 markdown，人只做最后审阅。

## 二、目标 / 非目标

- 目标：周报初稿 5 分钟内产出；数据来源可追溯到具体文件
- 非目标：不做可视化看板；不接管发送环节

## 三、步骤总表

| id | 名称 | 依赖 | 状态 | 验收要点 | 分文档 |
|----|------|------|------|---------|--------|
| 01-scope | 范围确认 | - | done | 数据源清单无遗漏，边界经用户确认 | steps/01-scope/step.md |
| 02-design | 方案设计 | 01-scope | execute | 两个方案对比，取舍理由可复述 | steps/02-design/step.md |
| 03-build | 脚本实现 | 02-design | draft | 单命令跑出初稿，字段零缺失 | steps/03-build/step.md |

## 四、文档注册表

| 路径 | 职责 | 状态 | 最后校验 |
|------|------|------|---------|
| steps/01-scope/step.md | 范围与数据源 | done | 2026-10-28 20:40 |
| steps/02-design/step.md | 方案对比与选型 | execute | 2026-10-28 21:05 |

## 五、决策索引

- D-01 只读外部数据源，不落副本 → 见 decisions.md
- D-02 输出走本地 markdown，不走在线文档 → 见 decisions.md

## 六、风险与 Plan B

- 风险：数据源格式变动会导致解析失败 → Plan B：解析层做字段级容错，缺字段留空并告警
