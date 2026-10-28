# 03-build 脚本实现

> parent: ../../plan.md
> status: draft
> updated: 2026-10-28 21:05
> upstream_check: -
> pending_sync: 无

## 目标

一条命令产出周报初稿，字段零缺失。

## 输入

- `02-design` 选定的方案
- 各数据源的解析规则（后续登记到 refs.md）

## 输出

`work/` 下为中间解析结果；最终稿 `output/weekly_report-<YYYYMMDD>.md`。

## 执行标准

- [ ] 机械项：单命令运行退出码 0
- [ ] 机械项：生成的初稿字段数与 `01-scope` 清单一致
- [ ] 人工项：初稿读起来像人写的，不需要重排结构

## 执行记录

- （未开工）
